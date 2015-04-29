#! /usr/bin/env python
# -*- coding:utf-8 -*-
# ahthor:zhouzh
# Program Featrue:Grab Grils Pictrues of http://www.7160.com

import argparse
import urllib
import re
import os
import threading
import Queue
import logging
import time
import sys
import socket

def setcmdargs():
	"""使用argparse模块设置并返回命令行参数"""
	parser=argparse.ArgumentParser(description=u"从指定的网站收集美女图片")
	parser.add_argument("-u",type=str,default="www.7160.com",help=u"指定提供美女图片的网站")
	parser.add_argument("-n",type=int,default=10,help=u"指定并发线程数目")
	parser.add_argument("-d",type=str,default="pics",help=u"指定美女图片的存储位置")
	parser.add_argument("-l",type=int,default=sys.maxsize,help=u"指定要收集的图片数目")
	args=parser.parse_args()
	return args

def progressbar(pool):
	"""显示和更新下载进度条"""
	str=u"\r下载进度:已下载写真集%d套,共%d张图片" %(pool.albumsdowned,pool.picsdowned)
	seemlength=len(str)
	realength=seemlength+(len(str.encode("utf-8"))-seemlength)/2
	sys.stdout.write(str+" "*(80-realength))
	sys.stdout.flush()

def getpage(url):
	"""根据url请求页面并记录相应的日志"""
	times=1
	while(times<6):  # 网络请求失败后最多重复五次
		try:
			page=urllib.urlopen(url)
			pagehtml=page.read()
			pagehtml=pagehtml.decode("gbk").encode("utf-8")  # 将gb2312编码转为utf-8
			return pagehtml
		except IOError:
			if(times<5):
				times+=1
			else:
				return None
	
def invokespider(site,threadnum,storedir,picsnum):
	"""根据命令行参数的值对程序进行初始化设置并启动程序
	site:目标网站url
	threadnum:并发线程数目
	storedir:存储路径
	picsnum:要收集的图片数量
	"""
	if(site[0:7]!="http://"):  # 如果site前面没有指定协议，那么给其加上"http://"
		site="http://"+site
	if(not os.path.isabs(storedir)):  # 如果storedir是一个相对路径，那么将storedir设置为当前运行目录的子目录
		os.chdir(os.path.dirname(__file__))
		storedir=os.path.abspath(storedir)
	if(not os.path.exists(storedir)):  # 如果storedir不存在，那么创建它
		try:
			os.makedirs(storedir)
		except IOError:
			print u"存储文件夹创建失败!"
			logging.warning("存储文件夹创建失败")
			exit()
	categoryqueue=Queue.Queue()	# 创建存储图集分类的队列
	pageHtml=getpage(site)
	if(not pageHtml):  # 请求网站首页失败，退出程序
		print u"请求%s失败." %(site)
		logging.warning("请求%s失败",site)
		exit()
	menuhtml=re.findall('<div class="nav">[\s\S]*?</div>',pageHtml)[0]
	categorylinks=re.findall("<a href='(.*?)' title=\"(.*?)\">",menuhtml)  # 提取图集分类的锚点
	for anchor in categorylinks:
		herf=site+anchor[0]
		text=anchor[1]
		categoryqueue.put((herf,text))  # 以(href,text)的形式将图集的分类锚点存入categoryqueue
	#  打印程序的基本设置信息
	print "*"* 22+"mmCrawler"+"*" * 22
	print u"目标网站:"+site
	print u"\n并发线程数:"+str(threadnum)
	print u"\n图片存储目录:"+storedir
	if(picsnum==sys.maxsize):
		print u"\n图片数量:没有限制"
	else:
		print u"\n图片数量:"+str(picsnum)
	print u"\n开始时间:"+time.ctime()
	sys.stdout.write(u"\n下载进度:已下载美女写真集0套,一共0张图片")
	sys.stdout.flush()
	logging.info("程序启动")
	pool=ThreadPool(site,categoryqueue,threadnum,storedir,picsnum)  # 创建线程池
	pool.start()  # 启动程序，开始运行
	pool.exit()  # 退出程序

class ThreadPool(threading.Thread):
	"""线程池类，继承自threading.Thread
	该类的实例负责管理所有的工作线程
	"""
	def __init__(self,site,categoryqueue,threadnum,storedir,picsnum):
		"""构造函数，创建管理线程并绑定一些必要的属性"""
		threading.Thread.__init__(self)
		self.site=site
		self.albumscategory=categoryqueue
		self.categorylock=False  # 对分类队列加锁,保证线程处理完图集分类的当前页后再开始下一页
		self.nextpagepage=None  # 图集分类的下一页
		self.curcategory=None  # 程序正在处理的图集分类
		self.page=1  # 程序正在处理的分类页面的页码
		self.albums=Queue.Queue()	# 以(text,href)的形式存储图集页面的文本和链接
		self.threadsnum=threadnum;	# 线程数量
		self.storedir=storedir	# 图片存储目录
		self.picsnum=abs(picsnum)  # 图片数量
		self.picsdowned=0	# 已经下载的图片数量
		self.albumsdowned=0  # 已经下载的图集数目
		self.threads=[]  # 线程池里面的工作线程
		while(len(self.threads)<self.threadsnum):  # 创建工作线程
			self.threads.append(threading.Thread(target=grabgirls,args=(self,)))
			
	def run(self):
		threads=self.threads
		for thread in threads:
			thread.setDaemon(True)  # 设置线程的daemon=True方便程序退出
			thread.start()
	
	def exit(self):
		"""线程退出"""
		while((not self.albumscategory.empty()) and self.picsdowned<self.picsnum):  #  阻塞线程池线程直至任务完成
			time.sleep(25)
		print u"\n\n下载完毕!"+u"\n\n结束时间:"+time.ctime()
		print "*"*53
		logging.info("下载结束!")
		exit()

def grabgirls(pool):
	"""为工作线程分配任务
	工作线程不断轮询直至程序任务完成
	任务优先级：下载图片>从分类页面中提取图集>下载分类页面
	"""
	while True:
		if(not pool.albums.empty()):
			album=pool.albums.get()
			downloadpic(pool,album)
		elif(not pool.albumscategory.empty() and not pool.categorylock):
			pool.categorylock=True
			if(pool.curcategory):	
				category=pool.curcategory
			else:
				category=pool.albumscategory.get()
				pool.curcategory=category
				pool.page=1
			extractalbums(pool,category)
		else:
			time.sleep(5)

def extractalbums(pool,category):
	"""从分类页面中提取图集锚点"""
	categorytext=category[1]
	os.chdir(pool.storedir)
	categorydir=os.path.abspath(categorytext.decode("utf-8"))
	if(not os.path.exists(categorydir)):  # 创建分类目录
		os.makedirs(categorydir)
	categoryurl=category[0]
	page=pool.page
	if(page>1):
		categoryurl=pool.nextpageurl
	pagehtml=getpage(categoryurl)
	if(not pagehtml):  # 请求分类页面失败，退出函数
		pool.categorylock=False
		logging.warning("请求分类页面失败%s",categoryurl)
		return
	albumslist=re.findall('<dl class="r1_l">[\s\S]*?</dl>',pagehtml)  # 提取包含图集的html
	if(len(albumslist)>0):  # 如果albumslist存在，说明是一个有效的分类页面
		logging.info("开始下载%s的第%d页",categorytext,page)
		albums=re.findall('<p><a href="(.*?)" title="(.*?)">.*?</p>',albumslist[0])  # 提取图集的锚点
		for anchor in albums:
			herf=pool.site+anchor[0]
			text=re.sub('[\"\\\\/\*:\|\?><]','',anchor[1])  # 去掉windows文件夹名称中不允许的字符
			pool.albums.put((text,herf))
		pool.page+=1
		nextpageurl=re.findall("<a href='(.*?)'>下一页</a>",albumslist[0])
		pool.nextpageurl=os.path.dirname(categoryurl)+"/"+nextpageurl[0]
	else:  #  如果albumslist不存在，说明该分类下面的图集已经处理完毕
		pool.curcurrent=None
		pool.nextpageurl=None
	pool.categorylock=False  # 释放分类队列的锁
		
def downloadpic(pool,album,threadata=None):
	"""从图集页面中提取图片的链接"""
	if(pool.picsdowned>=pool.picsnum):  # 任务完成，阻塞线程
		while(True):
			time.sleep(5)
	pool.picsdowned+=1  # 下载图片前先使已下载图片数量加一，以防文件名重叠
	albumtext=album[0]
	if(threadata):  #  如果threadata不为None,说明当前处理的不是图集的第一页
		albumdir=threadata.albumdir
		filename=os.path.join(albumdir,str(pool.picsdowned)+".jpg")
		albumurl=threadata.nextpage
	else:
		albumurl=album[1]
		os.chdir(os.path.join(pool.storedir,pool.curcategory[1]).decode("utf-8"))
		albumdir=os.path.abspath(albumtext.decode("utf-8"))
		filename=os.path.join(albumdir,str(pool.picsdowned)+".jpg")
		if(not os.path.exists(albumdir)):
			os.makedirs(albumdir)
			pool.albumsdowned+=1
			progressbar(pool)
		threadata=threading.local()  #  创建线程局部数据块并存储当前图集对应的目录
		threadata.albumdir=albumdir
	pagehtml=getpage(albumurl)
	if(not pagehtml):
		logging.warning("下载%s失败!",albumurl)
		return
	logging.info("开始下载%s[%s]",albumtext,albumurl)
	picurl=re.findall("<img src='(.*?)' border='0' [\s\S]*?/>",pagehtml)[0]
	retrievepic(pool,picurl,filename)
	nextpage=re.findall("<a href='(index_\d+\.html)'>下一页</a>",pagehtml)  #  提取图集下一页的锚点
	if(len(nextpage)>0):  #  如果存在下一页的锚点，说明还没有到达图集最后一页，线程递归处理
		nextpage=nextpage[0]
		threadata.nextpage=os.path.dirname(albumurl)+"/"+nextpage
		downloadpic(pool,album,threadata)
	else:  # 处理完图集的最后一页，退出函数，线程重新获取任务
		return

def retrievepic(pool,picurl,filename):
	"""将图片下载到本地磁盘"""
	times=1
	while(times<6):
		try:
			urllib.urlretrieve(picurl,filename)
			progressbar(pool)
			break
		except IOError:
			if(times<5):
				times+=1
			else:
				logging.warning("下载图片失败%s",picurl)
				return 

if __name__=="__main__":
	logfile=os.path.join(os.path.dirname(__file__),"spider.log")  #  程序日志文件保存于当前运行目录
	logging.basicConfig(filename=logfile,level=logging.DEBUG,format="%(levelname)s %(asctime)s %(filename)s [line:%(lineno)d]\
	%(threadName)s %(message)s",datefmt="%a, %d %b %Y %H:%M:%S")  # 设置日志打印格式
	socket.setdefaulttimeout(10)
	cmdargs=setcmdargs()
	invokespider(cmdargs.u,cmdargs.n,cmdargs.d,cmdargs.l)

	
	
		
	


	
	
	
	

	
	
	
	
	

	
	
	
	
	
	





	
	


#! /usr/bin/env python
# -*- coding:utf-8 -*-
# ahthor:zhouzh
# Program Featrue:Grab Grils Pictrues of http://www.22mm.cc

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
	parser.add_argument("-u",type=str,default="www.22mm.cc",help=u"指定提供美女图片的网站")
	parser.add_argument("-n",type=int,default=10,help=u"指定并发线程数目")
	parser.add_argument("-d",type=str,default="pics",help=u"指定美女图片的存储位置")
	parser.add_argument("-l",type=int,default=sys.maxsize,help=u"指定要收集的图片数目")
	args=parser.parse_args()
	return args

def progressbar(pool):
	"""显示和更新下载进度"""
	str=u"\r下载进度:已下载写真集%d套,共%d张图片" %(pool.albumsdowned,pool.picsdowned)
	seemlength=len(str)
	realength=seemlength+(len(str.encode("utf-8"))-seemlength)/2
	sys.stdout.write(str+" "*(80-realength))
	sys.stdout.flush()

def getpage(url):
	"""根据url请求页面并记录相应的日志"""
	times=1
	while(times<6):  # 网络请求失败后最多重复三次
		try:
			page=urllib.urlopen(url)
			pagehtml=page.read()
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
			os.makedirs(storedir.decode("utf-8"))
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
	menuHtml=re.findall('<div class="inner_menu">.*?<\/div>',pageHtml)[0]  # 提取包含图集分类的html	
	categoryLink=re.findall('<a href="(/mm/.*?)" >(.*?)</a>',menuHtml)[0:4]  # 提取图集分类的锚点
	for anchor in categoryLink:
		herf=site+anchor[0]
		text=anchor[1]
		categoryqueue.put((herf,text))  # 以(href,text)的形式将图集的分类锚点存入categoryqueue
	#  打印程序的基本设置信息
	print "*"* 22+"mmCrawler"+"*" * 22
	print u"目标网站:"+site
	print u"\n并发线程数:"+str(threadnum)
	print u"\n图片存储目录:"+storedir
	if(picsnum!=sys.maxsize):
		print u"\n图片数量:"+str(picsnum)
	else:
		print u"\n图片数量:没有限制"
	print u"\n开始时间:"+time.ctime()
	sys.stdout.write(u"\n下载进度:已下载写真集0套，一共0张图片")
	sys.stdout.flush()
	logging.info("程序启动")
	pool=ThreadPool(site,categoryqueue,threadnum,storedir,picsnum)  # 创建线程池
	pool.start()  # 启动程序，开始运行
	pool.exit()  # 停止程序

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
		self.curcategory=None  # 程序正在处理的图集分类
		self.page=1  # 程序正在处理的分类页面的页码
		self.albums=Queue.Queue()	# 以(text,href)的形式存储图集页面的文本和链接
		self.albumspics=Queue.Queue()  # 以{text:[href,...]}的形式存储图集的文本和对应的图片链接
		self.pics=Queue.Queue()  # 图片的链接
		self.threadsnum=threadnum;	# 线程数量
		self.storedir=storedir	# 图片存储目录
		self.picsnum=abs(picsnum)  # 图片数量
		self.picsdowned=0	# 已经下载的图片数量
		self.albumsdowned=0  # 已经下载完成的图集数目
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
			time.sleep(25)  # 线程阻塞时间设为25s,尽量等图片全部图片下载完再退出程序
		print u"\n\n下载完毕!"+u"\n\n结束时间:"+time.ctime()
		print "*"*53
		logging.info("下载结束!")
		try:
			exit()
		except BaseException:
			pass

def grabgirls(pool):
	"""为工作线程分配任务
	工作线程不断轮询直至程序任务完成
	任务优先级：下载图片>处理图集>提取图集内所有图片的链接>提取图集
	"""
	while True:
		if(not pool.albumspics.empty()):
			albumpics=pool.albumspics.get()
			downloadpic(pool,albumpics)
		elif(not pool.albums.empty()):
			album=pool.albums.get()
			extractpics(pool,album)
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
			time.sleep(10)

def extractalbums(pool,category):
	"""从分类页面中提取图集锚点"""
	categorytext=category[1]
	os.chdir(pool.storedir.decode("utf-8"))
	categorydir=os.path.abspath(categorytext).decode("utf-8")
	if(not os.path.exists(categorydir)):  # 创建分类目录
		os.makedirs(categorydir)
	categoryurl=category[0]
	page=pool.page
	if(page==1):
		suffix="index.html"
	else:
		suffix="index_"+str(page)+".html"
	pagehtml=getpage(os.path.join(categoryurl,suffix))
	if(not pagehtml):  # 请求分类页面失败，退出函数
		logging.warning("请求分类页面失败%s",categoryurl)
		return
	albumslist=re.findall('<div class="c_inner">.*?</div>',pagehtml)  # 提取包含图集的html
	if(len(albumslist)>0):  # len(albumslist)>0说明是有效的分类页
		logging.info("开始下载%s的第%d页",categorytext,page)
		albums=re.findall('<a href="(.*?)" title="(.*?)" target="_blank">',albumslist[1])  # 提取图集的锚点
		for anchor in albums:
			herf=pool.site+anchor[0]
			text=re.sub('[\"\\\\/\*:\|\?><]','',anchor[1])  # 去掉windows文件夹名称中不允许的字符
			pool.albums.put((text,herf))
		pool.page+=1
	else:
		pool.curcategory=None
	pool.categorylock=False  # 释放分类队列的锁
		
def extractpics(pool,album):
	"""从图集页面中提取图片的链接"""
	albumtext=album[0]
	albumurl=album[1]
	pagehtml=getpage(albumurl)
	if(not pagehtml):  # 请求图集页面失败，退出函数
		logging.warning("下载%s[%s]失败",albumtext,albumurl)
		return
	picsnumber=re.findall('<strong class="diblcok"><span class="fColor">\d{1,100}</span>/(.*?)</strong>',pagehtml)[0]  # 获取图集的图片数目
	if(int(picsnumber)>1):  # 如果图集的页面数目大于一
		separateurl=os.path.splitext(albumurl)
		root=separateurl[0]+"-"+picsnumber
		ext=separateurl[1]
		lastpageurl=root+ext	# 获取图集最后一页的url,最后一页包含所有图片的url
		lastpagehtml=getpage(lastpageurl)
		if(not lastpagehtml):  # 请求图集最后一页失败，退出函数
			logging.warning("下载%s[%s]失败",albumtext,albumurl)
			return
	else:
		lastpagehtml=pagehtml
	logging.info("开始下载%s[%s]",albumtext,albumurl)
	list=[]
	picsurl=re.findall('arrayImg\[\d\]="(.*?)"',lastpagehtml)
	for url in picsurl:
		url=re.sub("big","pic",url)	# 将url中的"big"替换成"pic"得到正确的图片url
		list.append(url)
	dict={albumtext:list}
	pool.albumspics.put(dict)	# 以{text:[link,...]}的形式存入pool.albumspics

def downloadpic(pool,album,threadata=None):
	"""创建图集目录并且下载图集"""
	if(pool.picsdowned>=pool.picsnum):  # 任务完成，阻塞线程
		while True:
			time.sleep(10)
	albumtext=album.keys()[0]
	if(threadata):  # 如果threadata不为None，说明处理的不是图集的第一张图片
		albumdir=threadata.albumdir
		picurl=threadata.picsurl[0]
	else:
		picsurl=album.values()[0]
		picurl=picsurl[0]
		os.chdir(os.path.join(pool.storedir,pool.curcategory[1]).decode("utf-8"))
		albumdir=os.path.abspath(albumtext.decode("utf-8"))
		if(not os.path.exists(albumdir)):
			os.makedirs(albumdir)
			pool.albumsdowned+=1
		threadata=threading.local()
		threadata.albumdir=albumdir
		threadata.picsurl=picsurl
	pool.picsdowned+=1
	filename=os.path.join(albumdir,str(pool.picsdowned)+".jpg")
	retrievepic(pool,picurl,filename)
	if(len(threadata.picsurl)>1):  #  图集下载未完成，线程递归处理
		threadata.picsurl=threadata.picsurl[1:]
		downloadpic(pool,album,threadata)
	else:
		return 
	
def retrievepic(pool,picurl,filename):
	"""下载图片到本地磁盘"""
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
				logging.warning("图片下载失败[%s]",picurl)
				return

if __name__=="__main__":
	logfile=os.path.join(os.path.dirname(__file__),"spider.log")  #  程序日志文件保存于当前运行目录
	logging.basicConfig(filename=logfile,level=logging.DEBUG,format="%(levelname)s %(asctime)s %(filename)s [line:%(lineno)d]\
	%(threadName)s %(message)s",datefmt="%a, %d %b %Y %H:%M:%S") 
	socket.setdefaulttimeout(10)  # 设置socket连接超过10秒为超时
	cmdargs=setcmdargs()
	invokespider(cmdargs.u,cmdargs.n,cmdargs.d,cmdargs.l)

	
	
	
	

	
	
	
	
	

	
	
	
	
	
	





	
	


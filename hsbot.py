#!/usr/bin/python
# -*- coding: utf-8 -*-
import json,os,thread,sys,logging,socket,json
from thread import start_new_thread as thread
from subprocess import call
from time import sleep,localtime,time
from Tkinter import *
from random import randint

from telegram import Updater,Bot
from optparse import OptionParser

import paho.mqtt.client as mossub
import paho.mqtt.publish as mospub

import RPi.GPIO as g

import config as c

lastStatusCh = 0 # wann das letzte mal der space status geändert wurde

#gpio einstellungen
g.setwarnings(False)
g.setmode(g.BOARD)

def setTopic(tpc):
	pass
	
def incMsg(msg,nick=''):
	if not nick == '':
		msg = nick+": "+msg
	#todo

def debugMsg(msg,fkt=''):
	pl = "["+str(fkt)+"]: "+str(msg)
	mospub.single(c.MQTTDEBU, payload=pl, hostname=c.MQTTSRV)

class MQTT():
	client = mossub.Client()
	
	def __init__(self):
		self.client = mossub.Client()
		self.client.on_connect = self.on_connect
		self.client.on_message = self.on_message

		self.client.connect(c.MQTTSRV, 1883, 60)
		
	def run(self):
		while True:
			self.client.loop_forever()

	def on_connect(self,client, userdata, flags, rc):
		print("MQTT Start: "+str(rc))
		self.client.subscribe(c.MQTTTOPI)
		self.client.subscribe(c.MQTTTOPT)

	def on_message(self,client, userdata, msg):
		print("MQTT Msg: "+msg.topic+" "+str(msg.payload))
		if(msg.topic == 'toast'):
			befehle.toast(msg.payload,10)
		
		if(msg.topic == 'chat'):
			sendMsg(str(msg.payload),'mqtt',"[MQTT]")
		
	def incMsg(msg,nick=''):
		pass

class Telegram():
	FOLLOWER = ()
	NAME = "telegram"

	def __init__(self):
		updater = Updater(token=c.TOKEN)
		dispatcher = updater.dispatcher
		f = open(c.TFILE, 'r')
		self.FOLLOWER = f.read().split(",")
		f.close()
		if "" in self.FOLLOWER:
			while "" in self.FOLLOWER:
				self.FOLLOWER.remove("")
			f = open(c.TFILE, 'w')
			f.write(",".join(self.FOLLOWER))
			f.close()

		dispatcher.addTelegramCommandHandler('delete', self.deleteme)
		dispatcher.addTelegramCommandHandler('add', self.addme)
		dispatcher.addTelegramMessageHandler(self.echo)
		dispatcher.addUnknownTelegramCommandHandler(self.notunderstand)

		start_new_thread(updater.start_polling,(5,))

	def echo(self,bot, update):
		#print(update)
		sID = str(update.message.chat.id)
		sName = update.message.chat.first_name
		sText = update.message.text
		#TODO hier fehlt irgendwie die sender var
		print(sID)
		print(sName)
		print(sText)
		self.sendPublic(sName+": "+sText,bot,sID)
		self.toController(sText,sName)

	def deleteme(self,bot,update):
		#print("d")
		user = str(update.message.chat_id)
		#print("user: "+user)
		#print("follower: "+str(self.FOLLOWER))
		if user in self.FOLLOWER:
			#print("ja")
			while user in self.FOLLOWER:
				self.FOLLOWER.remove(user)
				print("entferne")
			f = open(c.TFILE, 'w')
			f.write(",".join(self.FOLLOWER))
			f.close()
			#print("follower: "+str(self.FOLLOWER))
			self.sendPrivat(update.message.chat_id,"Bis Bald ...",bot)
		else:
			self.sendPrivat(update.message.chat_id,"Du bist nicht in meiner Liste.",bot)

	def addme(self,bot,update):
		#print("a")
		user = str(update.message.chat_id)
		if user in self.FOLLOWER:
			self.sendPrivat(update.message.chat_id,"Du bist schon in meiner Liste.",bot)
			
		else:
			f = open(c.TFILE, 'a')
			if len(self.FOLLOWER) == 0:
				f.write(str(user))
			else:
				f.write(","+str(user))                  
			f.close()
			self.FOLLOWER.append(user)
			#print("follower: "+str(self.FOLLOWER))
			self.sendPrivat(update.message.chat_id,"Du wurdest hinzugefügt.",bot)

	def notunderstand(self,bot,update):
		bot.sendMessage(chat_id=update.message.chat_id, text="/add : dich anmelden\n/delete : dich abmelden")

	def sendPublic(self,sendtext,bot=False,sender=0):
		#print("3")
		if not bot:
			#print("6")
			bot = Bot(token=c.TOKEN)
		#print("7")
			
		if sender == 0 or sender in self.FOLLOWER:
			#print("4")
			for i in self.FOLLOWER:
				if i != sender:
					#print("1")
					bot.sendMessage(chat_id=i, text=sendtext)
		else:
			#print("5")
			self.sendPrivat(sender,"Du bist nicht teil der Gruppe: tippe /add um beizutreten",bot)

	def sendPrivat(self,reciever,sendtext,bot=False):
		if not bot:
			bot = Bot(token=c.TOKEN)
		#print("Privat: "+sendtext)
		bot.sendMessage(chat_id=reciever, text=sendtext)

	def heartbeat(self):
		return True
	
	def sendTo(self,nick,uid,text):
		if nick == c.JNICK:
			txt = text
		else:
			txt = nick +": "+ text
			
		self.sendPublic(txt)
		
	def toController(self,text,nick):
		HOST = '127.0.0.1'
		PORT = c.CMSGPORT
		
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((HOST, PORT))
			data = {'service':self.NAME,'text':str(text),'nick':str(nick)}
			s.sendall(json.dumps(data))
			data = s.recv(1024)
			s.close()
			return data
		except Exception as e:
			print("ERROR")
			print(e)
			print(sys.exc_info()[0])	
			return False


				
# diese klasse überwacht alle GPIO ports und reagiert nach wunsch
class IOPorts():
	blinking = False

	def __init__(self):
		g.setup(11, g.OUT) #Botlampe
		g.setup(15, g.IN, pull_up_down=g.PUD_UP) #Botschalter Hi=off
		
		g.add_event_detect(15, g.BOTH, callback=self.doSpaceStatus, bouncetime=300)
	
	def blinking(self,interval,ratio):
		while self.blinking:
			a = interval*ratio
			b = interval-a
			g.output(11,1)
			sleep(a)
			g.output(11,0)
			sleep(b)
		
	def blink_start(self,interval,ratio=0.5):
		self.blinking = True
		thread(self.blinking,(interval,ratio))

	def blink_stop(self):
		self.blinking = False
	
	
	def doSpaceStatus(self,ch):
		if g.input(15):
			# in chat schreiben, dass spcae geschlossen
			#sendMsg("Der space ist nun geschlossen.")
			sleep(5)
			#monitor on 
			call(["./monitor.sh","off"])
			
			# spacestatus close
			call(['curl','-d status=close', "https://hackerspace-bielefeld.de/spacestatus/spacestatus.php"])
			
			# port 15 off
			g.output(11,0)
		else:
			#monitor on 
			call(["./monitor.sh","on"])
			# etwas show
			#jabber.disconnect()
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			g.output(11,1)
			sleep(0.1)
			g.output(11,0)
			sleep(0.1)
			
			
			#jabber.newSession()
			# spacestatus open
			call(['curl','-d status=open', "https://hackerspace-bielefeld.de/spacestatus/spacestatus.php"])
			
			# port 11 on
			g.output(11,1)
			
			sleep(5)
			# in chat schreiben, dass space offen
			#sendMsg("Der Space ist nun geöffnet.")

# GUI anlegen
f = Tk()
h = f.winfo_screenheight()
w = f.winfo_screenwidth()

#Fenster
f.title('HSBot2')
f.geometry(str(w)+"x"+str(h)+"+0+0")
f.wm_overrideredirect(True)
f.resizable(False, False)
f.config(bg="#000000")

# Label-Variablen
ts = StringVar()
ts.set("XX:XX")

ti = StringVar()
ti.set("------------")

to = StringVar()
to.set("TOAST")

#Textfelder
chat = Text(f,bg="#000000",fg="#ffffff",font=("Arial",32),bd=2,height=20,width=29)
clock = Label(f,textvariable=ts,fg="#ffffff", bg="#000000", bd=2,font=("Arial",108),width=5)
infoh = Label(f,textvariable=ti,fg="#ffffff", bg="#000000",font=("Arial",32))
infot = Text(f,bg="#000000",fg="#ffffff",font=("Arial",24),bd=2,height=19,width=22)	
toast = Label(f,textvariable=to,fg="#ffffff", bg="#000000", bd=2,font=("Arial",108),width=8)

chat.tag_add("all", "1.0", END)
chat.tag_config("all",wrap=WORD)
chat.grid(row=0,column=0,rowspan=3,sticky=NW)

# Clock
clock.grid(row=0,column=1,sticky=NE)

# Info Header
infoh.grid(row=1,column=1,sticky=S)

# Info Text
infot.tag_config("all",wrap=WORD)
infot.grid(row=2,column=1,sticky=SE)
f.rowconfigure(2, minsize=548)

data = "Chatfenster"

def getClock():
	global ts
	while True:
		lt = localtime()
		ts.set("%02i:%02i" % (lt.tm_hour,lt.tm_min))
		#f.update_idletasks()
		sleep(5)

def getInfo():
	global infot 
	global infoh
	while True:
		infos = {}
		tmp = os.listdir(c.INFPATH)
		for i in tmp:
			if not i.startswith(".") and i.endswith('.txt'):
				with open (c.INFPATH+"/"+i, "r") as myfile:
					data="".join(myfile.readlines())
					infos[i[:-4]] = data
			
		for j in infos:
			infot.delete("1.0",END)
			infot.insert(END, infos[j])
			infot.tag_add("all", "1.0", END)
			ti.set(j)
			infot.update()
			sleep(10)

def makeToast(msg,time):
	global toast
	global to
	
	mospub.single(c.MQTTTOPTOUT, payload=msg, hostname=c.MQTTSRV)
	to.set(str(msg))
	toast.grid(row=0,column=0)
	sleep(time)
	toast.grid_remove()
			
def getMsg():
	global chat
	while True:
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.bind(('', 2550))
			s.listen(5)
			
			while True:
				conn, addr = s.accept()
				print 'Connected by', addr
				jsondata = conn.recv(10240)
				conn.close()
				
				data = json.loads(jsondata)
				print(data)
				if data['type'] == 'chat':
						
					chat.insert(END, data['msg'] + "\n")
					chat.tag_add("all", "1.0", END)
					chat.see(END)
					chat.update()
					
				if data['type'] == 'toast':
					thread(makeToast,(data['msg'],data['time']))

				f.update_idletasks()
		except:
			s.close()
	
def isup(hostname):
	if os.system("ping -c 1 " + hostname) == 0:
		return True;
	return False
	
io = IOPorts()
	
thread(getClock,())
thread(getInfo,())
thread(getMsg,())
mqtt = MQTT()
thread(mqtt.run,())




mainloop()

#!/usr/local/bin/python
#
import sip
import sys
import os
from PyQt5 import QtCore, QtGui, uic
import os, errno
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QApplication,QMessageBox
import numpy as np
import json
from functools import partial
from image import segment_mask,read_color_image,read_gray_image
from image import four_window_image,boundingbox_image
from image import  resize,to_qt
import scipy.misc

DIR = os.path.abspath(os.path.dirname(__file__))
QDialog, Ui_Dialog = uic.loadUiType(os.path.join(DIR, "labeling.ui"), resource_suffix='')
Switch = False
from PyQt5.QtCore import QTimer
from PIL.ImageQt import ImageQt



##### Globals #####
def _error(msg):
	msgBox = QMessageBox()
	msgBox.setIcon(QMessageBox.Critical)
	msgBox.setText(msg)  	
	msgBox.setWindowTitle("Alert")
	msgBox.setStandardButtons(QMessageBox.Close)
	retval = msgBox.exec_()
def notify(msg,ntype="error"):
	if ntype == "error":
		_error(msg)
def getDirBrowser():
	dialog = QtWidgets.QFileDialog()
	dialog.setFileMode(QtWidgets.QFileDialog.Directory)
	dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
	directory = dialog.getExistingDirectory(None, 'Choose Directory', os.path.curdir)
	return str(directory)
def saveFileBrowser():
	fileName = QtWidgets.QFileDialog.getSaveFileName(None, 'Save Project', '.')
	return fileName
def openFileBrowser():
	fileName = QtWidgets.QFileDialog.getOpenFileName(None, 'Open Project', '.')
	return fileName
def brawse(btype = "folder"):
	if btype == "folder":
		return getDirBrowser()
	elif btype == "savefile":
		return saveFileBrowser()
	elif btype == "openfile":
		return openFileBrowser()

def mkdir(path):
	try:
	    os.makedirs(path)
	except OSError as e:
		if e.errno != errno.EEXIST:
			raise

##### Classes #####
class Contour:
	def __init__(self, cid,points=[],boundingbox = [],label=None,labelIndex=None,detailimage=None,pubishableimage=None):
		self._id = cid
		self._points = points
		self._label = label
		self._labelIndex = labelIndex
		self._detailimage = detailimage
		self._boundingbox = boundingbox
		self._publishable_image = pubishableimage

	def set_label(self,label,labelIndex):
		self._label = label
		self._labelIndex = labelIndex
	
	def get_label(self):
		return self._label
	
	def is_labeled(self):
		return self._label is not None

	def set_points(self,points):
		self._points = points
	
	def get_detail_image(self,img,mask):
		if self._detailimage is None:
			self._detailimage = four_window_image(img.copy(),mask.copy(),self._points,self._boundingbox)
		return self._detailimage
	
	def get_publishable_image(self,img,mask):
		if self._publishable_image is None:
			self._publishable_image = boundingbox_image(img.copy(),self._boundingbox)
		return self._publishable_image

	def get_points(self,points):
		return self._points
	
	@classmethod 
	def create(cls,json):
		c = Contour(json["Id"],np.array(json["Points"]),json["BoundingBox"],json["Label"],json["LabelIndex"])
		return c
	
	def to_json(self):
		json = {}
		json["Id"] = self._id
		json["Points"] = self._points.tolist()
		json["Label"] = self._label
		json["LabelIndex"] = self._labelIndex
		json["BoundingBox"] = self._boundingbox
		return json

class Image:
	def __init__(self,iid, path=None,contours=None):
		self._id = iid
		self._path = path
		if contours:
			self._contours = contours
		else:
			self._contours = []
		self._color_path = path
		self._mask_path = path.replace("_color.jpg","_mask.png")
		self._segmented = False
		self._color_image = read_color_image(self._color_path)
		self._mask_image = read_color_image(self._mask_path)
		self._name = os.path.basename(path).replace(".jpg","")
	
	def set_contours(self,contours):
		self._contours = contours
	
	def get_contours(self):
		return self._contours
	
	def segment(self):
		segments = segment_mask(self._color_image,self._mask_image)
		self._contours = []
		for i,s in enumerate(segments):
			self._contours.append(Contour(i,s[0],s[1]))
		self._segmented = True

	def segmented(self):
		return self._segmented
	
	def add_contour(self,points,label=None):
		self._contours.append(Contour(len(self._contours),points,label))
	
	def get_detail_image(self,cid):
		return self._contours[cid].get_detail_image(self._color_image,self._mask_image)

	def get_label(self,cid):
		return self._contours[cid].get_label()
	
	def label_contour(self,cid,label,labelIndex):
		self._contours[cid].set_label(label,labelIndex)

	def get_contour(self,cid):
		print(cid)
		return self._contours[cid]
	
	def is_labeled(self):
		labeled_contours = [c.is_labeled() for c in self._contours]
		numOflabeled = sum(labeled_contours) 
		if numOflabeled <= 0:
			return 0
		elif numOflabeled < len(self._contours):
			return 1
		else:
			return 2

	def num_of_contours(self):
		return len(self._contours)

	def get_image_paint(self,cid):
		if cid == -1:
			return self._color_image
		else:
			return self.get_detail_image(cid)

	@classmethod
	def create(cls,json):
		img = Image(json["Id"],json["Path"])
		
		for c in json["Contours"]:
			img._contours.append(Contour.create(c))
		return img
	
	def to_json(self):
		json = {}
		json["Id"] = self._id
		json["Path"] = self._path
		json["Contours"] = [c.to_json() for c in self._contours]
		return json

	def publish(self,path,newIndex=None):
		for i,c in enumerate(self._contours):
			if c.get_label() is None:
				continue
			img = c.get_publishable_image(self._color_image,self._mask_image)
			if newIndex:
				imgfilename = f"{path}/{newIndex[c._label]}.{c._label}/{self._name}_{c._id}_{c._label}.jpg"
			else:
				imgfilename = f"{path}/{c._labelIndex}.{c._label}/{self._name}_{c._id}_{c._label}.jpg"
			scipy.misc.imsave(imgfilename, img)

class Dataset:
	def __init__(self,oPath):
		self._path = oPath
		self._rowdataroot = None
		self._images = []
		self._images_names = []
		self._name = ""
		self._labels = []
	
	@property
	def name(self):
	    return self._name
	
	@property
	def count(self):
	    return len(self._images)
	
	@property
	def labels(self):
		return self._labels

	def num_of_contours(self,iid):
		return self._images[iid].num_of_contours()

	def get_label(self,iid,cid):
		return self._images[iid].get_label(cid)
	
	def get_labels(self):
		return self._labels

	def label_contour(self,iid,cid,label,labelIndex):
		self._images[iid].label_contour(cid,label,labelIndex)
	
	def is_labeled(self,iid):
		return self._images[iid].is_labeled()
	
	def get_contour(self,iid,cid):
		return self._images[iid].get_contour(cid)
	
	def get_image(self,iid):
		return self._images[iid]

	def get_image_paint(self,iid,cid):
		return self._images[iid].get_image_paint(cid)

	def get_images_names(self):
		return self._images_names

	def segment_image(self,iid):
		return self._images[iid].segment()

	@classmethod
	def load(cls,ofile):
		dataset = Dataset(ofile)
		with open(ofile,"r") as f:	
			dataset_json = json.loads(f.read())
			dataset._name = dataset_json["Name"]
			dataset._labels = dataset_json["Labels"]
			dataset._rowdataroot = dataset_json["Root"]
			for img in dataset_json["Images"]:
				img["Path"] = f"{dataset._rowdataroot}/{img['Path']}"
				print(img["Path"])
				_img = Image.create(img)

				dataset._images.append(_img)
				dataset._images_names.append(_img._name)

		return dataset
	
	def save(self):
		toSave = {}
		toSave["Name"] = self._name
		toSave["Images"] = [img.to_json() for img in self._images]
		toSave["Labels"] = self._labels
		with open(self._path,"w") as f:
			tjson = json.dumps(toSave,indent=2)
			f.write(tjson)

	def publish(self,path,newIndex=None):
		
		if newIndex is None:
			for i,l in enumerate(self._labels):
				mkdir(f'{path}/{i}.{l}')
		
		for img in self._images:
			if img.num_of_contours() > 0:
				img.publish(f'{path}/',newIndex)

class Project:
	def __init__(self,path=None,name=None,new=True):
		self._path = path
		self._name = name
		self._datasets = {}
		self._datasets_names = []

	@property 
	def numOfDatasets(self):
	    return len(self._datasets_names)
	
	def num_of_instance(self,dataset):
		return self._datasets[dataset].count

	def num_of_contours(self,dataset,iid):
		return self._datasets[dataset].num_of_contours(iid)

	def get_images_names(self,dataset):
		return self._datasets[dataset].get_images_names()

	def add_dataset(self,path):
		try:
			dataset = Dataset.load(path)
			self._datasets_names.append(dataset.name)
			self._datasets[dataset.name] = dataset
			return True
		except:
			raise
			return False
	
	def get_label(self,dataset, iid,cid):
		try:
			return self._datasets[dataset].get_label(iid,cid)
		except KeyError:
			return None

	def get_possible_labels(self,dataset):
		return self._datasets[dataset].get_labels()

	def is_labeled(self,dataset,iid):
		return self._datasets[dataset].is_labeled(iid)

	def get_contour(self,dataset,iid,cid):
		try:
			return self._datasets[dataset].get_contour(iid,cid)
		except KeyError:
			return []

	def get_image(self,dataset,iid):
		return self._datasets[dataset].get_image(iid)

	def get_image_paint(self,dataset,iid,cid):
		return self._datasets[dataset].get_image_paint(iid,cid)

	def get_dataset_names(self):
		return self._datasets_names
	
	def get_dataset_item(self,cid):
		return self._data[index]

	def segment_image(self,dataset,image):
		self._datasets[dataset].segment_image(image)

	def save(self,ofile=None):
		if not ofile and not self._path:
			return
		elif not ofile:
			ofile = self._path

		toSave = {}
		toSave["Datasets"] = [m._path for _,m in self._datasets.items()]
		toSave["Name"] = self._name
		with open(ofile,"w") as f:
			tjson = json.dumps(toSave,indent=2)
			f.write(tjson)
		
		for _,dataset in self._datasets.items():
			dataset.save()

		self._path = ofile

	@classmethod
	def load(cls,ofile):
		project = Project(ofile,new=False)
		with open(ofile,"r") as f:	
			project_json = json.loads(f.read())
			project._name = project_json["Name"]
			for dataset_path in project_json["Datasets"]:
				dataset = Dataset.load(dataset_path)
				project._datasets[dataset._name] = dataset
				project._datasets_names.append(dataset._name)
		return project
	
	def label_contour(self,dataset,iid,cid,label,labelIndex):
		self._datasets[dataset].label_contour(iid,cid,label,labelIndex)
	
	def publish_seperate(self,datasetpath):
		for _,dataset in self._datasets.items():
			path = f'{datasetpath}/{dataset.name}'
			mkdir(path)
			dataset.publish(path)

	def publish_togather(self,datasetpath):
		
		allLabels = []
		for _,dataset in self._datasets.items():
			allLabels += dataset.labels
		allLabelsIndex = {l:i for i,l in enumerate(set(allLabels))}
		for l,i in allLabelsIndex.items():
			path = f'{datasetpath}/{i}.{l}'
			mkdir(path)
		
		for _,dataset in self._datasets.items():
			dataset.publish(datasetpath,allLabelsIndex)

class Labeler(QDialog, Ui_Dialog):
	def __init__(self, parent=None):
		super(Labeler,self).__init__(parent)
		self.setupUi(self)

		self._openFlag = False
		self._project = None
		self._firstLoad = True
		self._selectedItem = -1
		self._selectedContour = -1
		self._labeledFlag = []
		self._current_dataset = None

		## Menu Actions
		self.actionNew_Project.triggered.connect(self.new_project)
		self.actionAdd_dataset.triggered.connect(self.add_dataset)
		self.actionSave_Project.triggered.connect(self.save_project)
		self.actionOpen_Project.triggered.connect(self.load_project)
		self.actionSPublish.triggered.connect(self.publish_seperate)
		self.actionAPublish.triggered.connect(self.publish_togather)

		# Push Button Actions
		self.pbNextContour.clicked.connect(self.next_contour)
		self.pbPreviousContour.clicked.connect(self.previous_contour)
		self.pbSegment.clicked.connect(self.segment)

		# Lists selection change actions
		self.cmb_dataset.currentIndexChanged.connect(self.on_datasetListSelectionChanged)
		self.listview_images.itemSelectionChanged.connect(self.on_imageListSelectionChanged)

	def refresh_labels_panel(self):
		# Adding Labels Buttons	
		labels = self._project.get_possible_labels(self._current_dataset)
		vbox = QVBoxLayout()
		for i,l in enumerate(labels):
			lblButton = QtWidgets.QPushButton(l)
			lblButton.setCheckable(True)
			lblButton.clicked.connect(partial(self.label_current,l,i))
			lblButton.setEnabled(False)
			vbox.addWidget(lblButton)
		vbox.addStretch(1)
		self.labelsGroup.setLayout(vbox)

	def refresh_labels_check(self,label):
		
		for btn in self.labelsGroup.findChildren(QtWidgets.QPushButton):
			if btn.text() == label:
				btn.setChecked(True)
				btn.setStyleSheet("""
						background-color:rgb(0, 170, 127)
					""")
			else:
				btn.setChecked(False)
				btn.setStyleSheet("")

	def refresh_imageList(self):
		self.listview_images.clear()
		self.listview_images.addItems(self._project.get_images_names(self._current_dataset))

	def refresh_frame_num(self):
		if self.listview_images.count() > 0:
			self.lbl_frame.setText(f"{self._selectedItem}/{self._project.num_of_instance(self._current_dataset)}")
		else:
			self.lbl_frame.setText("No images")

	def refresh_info(self):
		if self._selectedItem >= 0:
			img = self._project.get_image(self._current_dataset,self._selectedItem)
			self.lbl_info_dataset.setText(self._current_dataset)
			self.lbl_info_image.setText(img._name)
			## TODO: add isSegmented property
			if img.num_of_contours() > 0 and self._selectedContour >= 0:
				self.lbl_info_contour.setText(str(img.get_contour(self._selectedContour)._id))
				self.lbl_info_current_label.setText(img.get_contour(self._selectedContour)._label)
			else:
				self.lbl_info_contour.setText("")
				self.lbl_info_current_label.setText("")
		else:
			self.lbl_info_dataset.setText("")
			self.lbl_info_image.setText("")
			self.lbl_info_contour.setText("")
			self.lbl_info_current_label.setText("")

	def refresh_image(self):
		img = self._project.get_image_paint(self._current_dataset,self._selectedItem,self._selectedContour)
		
		qim = to_qt(resize(img,(780,480)))
		pix = QtGui.QPixmap.fromImage(qim)
		self.imgLbl.setPixmap(pix)

	def referesh_contour(self):
		self.refresh_contour_buttons()
		self.refresh_contour_num()

	def refresh_label(self):
		if self._selectedContour >= 0:
			currntLbls = self._project.get_label(self._current_dataset,self._selectedItem,self._selectedContour)
		else:
			currntLbls = None
		
		for btn in self.labelsGroup.findChildren(QtWidgets.QPushButton):
			if str(btn.text()) == currntLbls:
				btn.setChecked(True)
				btn.setStyleSheet("""
						background-color:rgb(0, 170, 127)
					""")
				btn.setEnabled(True)
			elif self._selectedContour < 0:
				btn.setChecked(False)
				btn.setStyleSheet("")
				btn.setEnabled(False)
			else:
				btn.setChecked(False)
				btn.setStyleSheet("")
				btn.setEnabled(True)
		
	def refresh_labeled(self,listitem=None):
		if listitem is not None:
			toberefreshed = [listitem]
		else:
			toberefreshed = range(0,self.listview_images.count())
		
		for i in toberefreshed:
			isl = self._project.is_labeled(self._current_dataset,i)
			if isl == 0:
				self.listview_images.item(i).setBackground(QtGui.QColor("white"))
			elif isl == 1:
				self.listview_images.item(i).setBackground(QtGui.QColor("yellow"))
			elif isl == 2:
				self.listview_images.item(i).setBackground(QtGui.QColor("green"))

	def refresh_contour_num(self):
		if self._selectedContour >= 0:
			self.lble_contourNum.setText(f"{self._selectedContour+1}/{self._project.num_of_contours(self._current_dataset,self._selectedItem)}")
			self.refresh_image()
			self.refresh_label()
			
		else:
			self.lble_contourNum.setText("Original images")
	
	def refresh_contour_buttons(self):
		lenc = self._project.num_of_contours(self._current_dataset,self._selectedItem)		
		if lenc == 0:
			self.pbSegment.setEnabled(True)
		else:
			self.pbSegment.setEnabled(False)
		if self._selectedContour == lenc - 1:
			self.pbNextContour.setEnabled(False)
		else:
			self.pbNextContour.setEnabled(True)

		if self._selectedContour >= 0:
			self.pbPreviousContour.setEnabled(True)
		else:
			self.pbPreviousContour.setEnabled(False)

	def refresh_view(self):
		self.refresh_labels_panel()
		self.refresh_imageList()
		self.refresh_frame_num()
		self.refresh_info()
		self.refresh_image()
		self.referesh_contour()
		self.refresh_labeled()

	def new_project(self):
		if self._openFlag:
			self.save_project()
		self._project = Project()
		# clearing
		self.enable_actions()
		self.enable_labels()
		self.cmb_dataset.clear()
		self.listview_images.clear()
		# reseting
		self._selectedItem = -1
	
	def save_project(self):
		# project has a path
		if self._project._path:
			self._project.save()
		# naver saved project
		else:
			oPath = brawse("savefile")
			if not oPath:
				return
			self._project.save(str(oPath[0]))

	def enable_actions(self):
		self.actionSave_Project_As.setEnabled(True)
		self.actionSave_Project.setEnabled(True)
		self.actionAdd_dataset.setEnabled(True)
		if self._project.numOfDatasets > 0:
			self.actionSPublish.setEnabled(True)
			self.actionAPublish.setEnabled(True)

	def enable_labels(self):
		for btn in self.labelsGroup.findChildren(QtWidgets.QPushButton):
			btn.setEnabled(True)

	def load_project(self):
		
		if self._openFlag:
			self.save_project()

		oPath = brawse("openfile")
		if not oPath  or oPath[0].strip()=='':
			return
		# loading project
		self._project = Project.load(str(oPath[0]))
		
		# clearing
		self.cmb_dataset.clear()
		self.listview_images.clear()

		if self._project.numOfDatasets > 0 :
			self.cmb_dataset.addItems(self._project._datasets_names)
			self.cmb_dataset.setCurrentIndex(0)
			self._current_dataset = self._project._datasets_names[0]

		self._openFlag = True

		self.enable_actions()
		# self.listview_data.addItems(self._project.get_data_names())
		# self.listview_data.setCurrentRow(0)
		# self.enable_actions()
		# self.enable_labels()
		# self.color_labeled()

	def add_dataset(self):
		
		oPath = brawse("openfile")
		if not oPath or oPath[0].strip()=='':
			return
		# adding dataset
		added = self._project.add_dataset(oPath[0])
		
		if not added:
			notify("Error while adding dataset.")
			return

		# clearing
		self.cmb_dataset.clear()

		# setting with the new
		self.cmb_dataset.addItems(self._project._datasets_names)
		
		if self._current_dataset:
			index = self.cmb_dataset.findText(self._current_dataset, QtCore.Qt.MatchFixedString)	
			self.cmb_dataset.setCurrentIndex(index)
		else:
			self.cmb_dataset.setCurrentIndex(len(self._project._datasets_names)-1)

	def segment(self):
		self._project.segment_image(self._current_dataset,self._selectedItem)
		
		self.refresh_contour_buttons()
		self.refresh_contour_num()

	def previous_contour(self):
		self._selectedContour -= 1
		self.referesh_contour()
		self.refresh_image()
		self.refresh_info()

	def next_contour(self):
		self._selectedContour += 1
		self.referesh_contour()
		self.refresh_image()
		self.refresh_info()

	def on_datasetListSelectionChanged(self):
		if self.cmb_dataset.count() == 0:
			return
		self._current_dataset = str(self.cmb_dataset.currentText())
		if self._project.num_of_instance(self._current_dataset) > 0:
			self._selectedItem = 0
			self._selectedContour = -1
		else:
			self._selectedItem = -1
			self._selectedContour = -1
		
		self.refresh_view()

	def on_imageListSelectionChanged(self):
		index = int(self.listview_images.currentRow())
		self._selectedItem = index
		if self._project.num_of_contours(self._current_dataset,self._selectedItem) > 0:
			self._selectedContour = -1
		else:
			self._selectedContour = -1

		self.refresh_frame_num()
		self.refresh_info()
		self.refresh_image()
		self.refresh_label()
		self.referesh_contour()
	
	def label_current(self,label,labelIndex):
		self._project.label_contour(self._current_dataset,self._selectedItem,self._selectedContour,label,labelIndex)
		
		self.refresh_labels_check(label)
		self.refresh_labeled(self._selectedItem)
		## TODO: do better job here
		if self.pbNextContour.isEnabled():
			self.next_contour()

	def publish_seperate(self):
		oPath = brawse("folder")
		if not oPath or oPath[0].strip()=='':
			return
		
		self._project.publish_seperate(os.path.abspath(oPath))
	
	def publish_togather(self,datasetPrefix):
		oPath = brawse("folder")
		if not oPath or oPath[0].strip()=='':
			return
		self._project.publish_togather(os.path.abspath(oPath))	

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	form = Labeler(None)
	form.show()
	sys.exit(app.exec_())

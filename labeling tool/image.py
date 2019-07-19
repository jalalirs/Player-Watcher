import cv2
import numpy as np
from PIL import Image
from PyQt5.QtGui import QImage

def resize(img,sz):
	img = cv2.resize(img,sz)
	return img

def to_pil(img):
	pil_im = Image.fromarray(img)
	return pil_im

def to_qt(img):
	pimg = to_pil(img)
	pimg = pimg.convert("RGB")
	data = pimg.tobytes("raw","RGB")
	qim = QImage(data, pimg.size[0], pimg.size[1], QImage.Format_RGB888)
	return qim

def mask_from_contour(contour,image):
	mask = np.zeros_like(image) # Create mask where white is what we want, black otherwise
	cv2.drawContours(mask, [contour], 0, 255, -1) # Draw filled contour in mask
	return mask

def subtract(img,mask):
	img[mask==0] = (0,0,0)
	return img

def crop_contour(img,rect):
	crop = img[rect[1]:rect[1]+rect[3],rect[0]:rect[0]+rect[2]]
	return crop

def find_countours(grayimg):
	if len(grayimg.shape) > 2:
		grayimg = grayimg[:,:,0]
	contours, hierarchy = cv2.findContours(grayimg,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
	return contours

def bounding_box(contour):
	contourPoly = cv2.approxPolyDP(contour, 3, True)
	boundRect = cv2.boundingRect(contourPoly)
	return boundRect

def boundingbox_image(img,boundingbox):
	img = crop_contour(img,boundingbox)
	return img

def four_window_image(img,mask,contour,boundRect):
	size = img.shape
	# colored image with selected contour
	img1 = cv2.drawContours(img.copy(), [contour], 0,(255, 0, 0), 3)

	# mask image with selected contour
	img2 = cv2.drawContours(mask, [contour], 0,(255, 0, 0), 3)

	# selected contour only from colored image
	maskfc = mask_from_contour(contour,mask[:,:,0])
	img3 = subtract(img.copy(),maskfc)
	
	# enlarged selected contour from img3 cropped with bounding box
	img4 = cv2.resize(crop_contour(img3,boundRect),(size[1],size[0]))

	# creating image with size 2*widthX2*height
	newImage = np.zeros((size[0]*2,size[1]*2,3)).astype(np.uint8)
	newImage[:size[0],:size[1]] = img1
	newImage[:size[0],size[1]:] = img2
	newImage[size[0]:,:size[1]] = img3
	newImage[size[0]:,size[1]:] = img4

	return newImage

def segment_mask(image,mask):

	if type(image) == str:
		image = cv2.imread(imagepath,cv2.COLOR_BGR2RGB)
	if type(mask) == str:
		mask = cv2.imread(maskpath)
		maskgray = cv2.cvtColor(mask,cv2.COLOR_BGR2GRAY)

	
	# skipping small contours
	contours = [c for c in find_countours(mask) if len(c) > 10]
	print(f"There are {len(contours)} contours")
	
	segments = []
	for i,c in enumerate(contours):
		if i%10 == 0:
			print(f"{i}/{len(contours)}")
		b = bounding_box(c)
		#img = four_window_image(image,mask,c,b)
		segments.append((c,b))

	return segments

def read_color_image(path):
	img = cv2.imread(path)
	return cv2.cvtColor(img,cv2.COLOR_BGR2RGB)

def read_gray_image(path):
	img = cv2.imread(path)
	gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
	return gray


def get_param():
	"""handle command line parameters, test using -h parameter...
	"""
	import argparse
	parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('-i', '--image', help='image path',default="imgs/")
	parser.add_argument('-m', '--mask', help='segment mask',default="imgs/")
	args = parser.parse_args()
	return args.image,args.mask

def main():
	
	imagepath,maskpath = get_param()
	segments = segment_mask(imagepath,maskpath)

	sz = (1920,1080)
	img = cv2.resize(segments[0][2],sz)
	cv2.imshow("Image",img)
	if cv2.waitKey(0) & 0xFF == ord('q'):
		exit()


if __name__ == "__main__":
	main()
	
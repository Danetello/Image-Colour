import numpy as np
import os
from PIL import Image

# File paths for where the images are stored and exported

fileListBase = []
fileListGrey = []
fileListMask = []

filePathBase = ""
filePathGrey = ""
filePathMask = ""
filePathOUT = ""

pathAbs = os.path.abspath(os.getcwd())

filePathBase = pathAbs + "\Textures_Base\\"
filePathGrey = pathAbs + "\Textures_Grey\\"
filePathMask = pathAbs + "\Textures_Mask\\"
filePathOUT = pathAbs + "\output\\"

def findFiles(filePath):
    fileList = []
    print(filePath)
    
    for root, dirs, files in os.walk(filePath):
        for file in files:
            # Append the file name to the list
            fileList.append(file)
    
    return fileList

# A one time process to find all the files inside the texture folders
fileListBase = findFiles(filePathBase)
fileListGrey = findFiles(filePathGrey)
fileListMask = findFiles(filePathMask)

def getNumberImages():
    return len(fileListBase)

def extractImage(type, position):
    """
    This function extracts the specified image from the selected folder and returns an
    RGB array of its colour values.
    
    Args:
        type (str): type specifier, whether the image is a base, grey or mask image 
        position (int): position of the image in the specified file list

    Returns:
        imageArray: a 3D np array of all the rgb values of the image
    """
    pathName = ""

    if (type == "base"):
        pathName = filePathBase + fileListBase[position]
    elif (type == "grey"):
        pathName = filePathGrey + fileListGrey[position]
    elif (type == "mask"):
        pathName = filePathMask + fileListMask[position]
        
    imageData = Image.open(pathName).convert('RGB')
    imageArray = np.asarray(imageData, dtype=np.uint64)
    
    return imageArray

def imageGenerate(imageData, position):
    
    imageArr = np.array(imageData, dtype= np.uint8)
    im = Image.fromarray(imageArr)
    im.save(filePathOUT + fileListBase[position][:-4] + ".png")
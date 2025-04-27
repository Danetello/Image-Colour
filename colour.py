import numpy as np
from PIL import Image
import os

def findFiles(filePath):
    fileList = []
    
    for root, dirs, files in os.walk(filePath):
        for file in files:
            # Append the file name to the list
            fileList.append(file)
    
    return fileList

path = os.path.abspath(os.getcwd())

# Find all the files in the input folder
filePathCC = path + "\Textures_cc\\"
filePathA = path + "\Textures_a\\"
filePathACC = path + "\Textures_acc\\"
filePathOUT = path + "\output\\"

filelistA = findFiles(filePathA)
filelistCC = findFiles(filePathCC)
filelistACC = findFiles(filePathACC)

def determineGardient(gradientInput, widthIn, lengthIn):
    """
    This function takes a grey scale image and calculated a single % value of how light that pixel is.
    This result is stored in a 2D list that is then returned, with each value representing a pixel

    Args:
        gradientInput (3D list): 3D list of the rgb values of the greyscale image
        widthIn (int): The width of the image
        lengthIn (int): The length of the image

    Returns:
        2D list: a list containing the lightness of each pixel
    """
    
    gradientList = np.array([[0]*widthIn]*lengthIn, dtype=np.uint64)
    gradientListIn = gradientInput[:]

    for length in range(0,lengthIn):
        for width in range(0,widthIn):
            totalColour = 0.0
            totalColour = gradientListIn[length][width][0] + gradientListIn[length][width][1] + gradientListIn[length][width][2]
            gradientColour = (totalColour / 765) * 10000
            if gradientColour >= 10000 :
                gradientColour = gradientColour - 10000
            gradientList[length][width] = gradientColour

    outputList = []

    for length in range(0,lengthIn):
        outputList.append(list(gradientList[length]))

    return outputList

def determineColour(colourInput, widthIn, lengthIn):
    """
    This function takes a coloured image and determine which pixel is 
    predominantly red, green or blue, based on the highest value in each pixel rgb.
    It then assigns r, g or b to that pixel

    Args:
        colourInput (3D list): 3D list of the rgb values of the colour image
        widthIn (int): The width of the image
        lengthIn (int): The length of the image

    Returns:
        2D list: a list containing the predominant colour of each pixel
    """
    
    red = 0
    green = 1
    blue = 2
    
    colourList = np.array([[""]*widthIn]*lengthIn)
    colourListIn = colourInput[:]

    for length in range(0,lengthIn):
        for width in range(0,widthIn):
            black = 0
            black = colourListIn[length][width][0] + colourListIn[length][width][1] + colourListIn[length][width][2]
            
            determinedColour = "R"
            
            if (black == 0):
                determinedColour = "N"
            elif (black == 765):
                determinedColour = "W"
            elif (colourListIn[length][width][0] >= colourListIn[length][width][1]) and (colourListIn[length][width][0] >= colourListIn[length][width][2]):
                determinedColour = "R"
            elif (colourListIn[length][width][1] >= colourListIn[length][width][0]) and (colourListIn[length][width][1] >= colourListIn[length][width][2]):
                determinedColour = "G"
            elif (colourListIn[length][width][2] >= colourListIn[length][width][0]) and (colourListIn[length][width][2] >= colourListIn[length][width][1]):
                determinedColour = "B"
            
            colourList[length][width] = determinedColour

    outputList = []

    for length in range(0,lengthIn):
        outputList.append(list(colourList[length]))

    return outputList

def recolourPixel(brightness, inputColour):
    """
        This function takes an imput colour an scales its brightness.
    Args:
        brightness (float): how close the pixel is to being white
        inputColour (list): rgb colour being scaled

    Returns:
        list: rgb list of scaled colour
    """
    
    # This is done as the darker a colour is, the more it should match the input colour 
    invertPercentage = 10000 - brightness
    outputColour = [0,0,0]
    
    for i in range(3):
        outputColour[i] = round(inputColour[i] * (invertPercentage/10000))

    # # Imperial
    # if sum(outputColour) < 10:
    #     outputColour[0] = (outputColour[0] + 240)    
    #     outputColour[1] = (outputColour[1] + 210)   
    #     outputColour[2] = (outputColour[2] + 60)    
    # elif sum(outputColour) < 60:
    #     outputColour[0] = (outputColour[0] + 220)    
    #     outputColour[1] = (outputColour[1] + 190)   
    #     outputColour[2] = (outputColour[2] + 50)    
    #     # for i in range(3):
    #     #     outputColour[i] = (outputColour[i] + 7) * 12
    # elif sum(outputColour) < 100:
    #     outputColour[0] = (outputColour[0] + 200)    
    #     outputColour[1] = (outputColour[1] + 170)   
    #     outputColour[2] = (outputColour[2] + 40)    
    #     # for i in range(3):
    #     #     outputColour[i] = (outputColour[i] + 7) * 10
    # elif sum(outputColour) < 140:
    #     outputColour[0] = (outputColour[0] + 180)    
    #     outputColour[1] = (outputColour[1] + 150)   
    #     outputColour[2] = (outputColour[2] + 30)    
    #     # for i in range(3):
    #     #     outputColour[i] = (outputColour[i] + 7) * 8
     
    # Ultra Marines
    # if sum(outputColour) < 10:
    #     outputColour[0] = (outputColour[0] + 10)    
    #     outputColour[1] = (outputColour[1] + 30)   
    #     outputColour[2] = (outputColour[2] + 160)    
    # elif sum(outputColour) < 20:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 7) * 3
    # elif sum(outputColour) < 30:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 6) * 2
    # elif sum(outputColour) < 40:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 3) * 3
    
    # Salamanders
    # if sum(outputColour) < 10:
    #     outputColour[0] = (outputColour[0] + 10)    
    #     outputColour[1] = (outputColour[1] + 60)    
    #     outputColour[2] = (outputColour[2] + 30)   
    # elif sum(outputColour) < 20:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 2) * 4
    # elif sum(outputColour) < 30:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 2) * 3
    # elif sum(outputColour) < 40:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 0) * 2

    # Templars light
    # if sum(outputColour) < 10:
    #     outputColour[0] = (outputColour[0] + 200)    
    #     outputColour[1] = (outputColour[1] + 200)    
    #     outputColour[2] = (outputColour[2] + 200)   
    # elif sum(outputColour) < 20:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 50) * 4
    # elif sum(outputColour) < 30:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 50) * 3
    # elif sum(outputColour) < 150:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 50) * 2
    
    # Templars Dark
    if sum(outputColour) < 10:
        outputColour[0] = (outputColour[0] + 0)    
        outputColour[1] = (outputColour[1] + 0)   
        outputColour[2] = (outputColour[2] + 0)    
    elif sum(outputColour) < 20:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 1) * 1
    elif sum(outputColour) < 30:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 1) * 1
    elif sum(outputColour) < 160:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 1) * 1

    return outputColour

def recolourPixelTrims(brightness, inputColour):
    """
        This function takes an imput colour an scales its brightness.
    Args:
        brightness (float): how close the pixel is to being white
        inputColour (list): rgb colour being scaled

    Returns:
        list: rgb list of scaled colour
    """
    
    # This is done as the darker a colour is, the more it should match the input colour 
    invertPercentage = 10000 - brightness
    outputColour = [0,0,0]
    
    for i in range(3):
        outputColour[i] = round(inputColour[i] * (invertPercentage/10000))
        
    if sum(outputColour) < 10:
        outputColour[0] = (outputColour[0] + 200)   # was 0
        outputColour[1] = (outputColour[1] + 200)   # was 0
        outputColour[2] = (outputColour[2] + 200)   # was 0
    elif sum(outputColour) < 20:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 100) * 2 # was 1) * 1
    elif sum(outputColour) < 30:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 100) * 2 # was 1) * 1
    elif sum(outputColour) < 40:
        for i in range(3):
            outputColour[i] = (outputColour[i] + 50) * 2 # was 1) * 1

    
    return outputColour

def recolourPixel2(brightness, inputColour):
    """
        This function takes an imput colour an scales its brightness.
    Args:
        brightness (float): how close the pixel is to being white
        inputColour (list): rgb colour being scaled

    Returns:
        list: rgb list of scaled colour
    """
    
    # This is done as the darker a colour is, the more it should match the input colour 
    invertPercentage = 10000 - brightness
    outputColour = [0,0,0]
    
    for i in range(3):
        outputColour[i] = round(inputColour[i] * (invertPercentage/10000))
        
    if sum(outputColour) < 10:
        outputColour[0] = (outputColour[0] + 110)   # was 0
        outputColour[1] = (outputColour[1] + 15)   # was 0
        outputColour[2] = (outputColour[2] + 15)   # was 0
    elif sum(outputColour) < 20:
        outputColour[0] = (outputColour[0] + 90)   # was 0
        outputColour[1] = (outputColour[1] + 15)   # was 0
        outputColour[2] = (outputColour[2] + 15)   # was 0
    elif sum(outputColour) < 30:
        outputColour[0] = (outputColour[0] + 70)   # was 0
        outputColour[1] = (outputColour[1] + 15)   # was 0
        outputColour[2] = (outputColour[2] + 15)   # was 0
    elif sum(outputColour) < 260:
        outputColour[0] = (outputColour[0] + 50)   # was 0
        outputColour[1] = (outputColour[1] + 15)   # was 0
        outputColour[2] = (outputColour[2] + 15)   # was 0

    
    return outputColour

def imageRecolour(colourSelect, colourMapIn, gradientPerMapIn, widthIn, lengthIn, newColour, greyArrayIn, colourArrayIn):
        
    recolouredImage = np.array([[[0,0,0]]*widthIn]*lengthIn, dtype=np.uint64)
    colourList = colourMapIn[:]
    gradientList = gradientPerMapIn[:]

    for length in range(0,lengthIn):
        for width in range(0,widthIn):
            if (colourList[length][width] == "R"):
                # recolouredImage[length][width] = recolourPixel(gradientList[length][width], newColour)[:]
                # recolouredImage[length][width] = recolourPixel(gradientList[length][width], decalColourDark)[:]
                recolouredImage[length][width] = recolourPixelTrims(gradientList[length][width], decalColourLight)[:]
                
            elif (colourList[length][width] == "W"):
                recolouredImage[length][width] = recolourPixel(gradientList[length][width], [145,15,15])[:]
            elif (colourList[length][width] == "G"):
                # recolouredImage[length][width] = recolourPixelTrims(gradientList[length][width], decalColourLight)[:]
                recolouredImage[length][width] = recolourPixel(gradientList[length][width], decalColourDark)[:]
                
            elif (colourList[length][width] == "B"):
                # recolouredImage[length][width] = recolourPixel(gradientList[length][width], decalColourLight)[:]
                # recolouredImage[length][width] = recolourPixel(gradientList[length][width], decalColourDark)[:]
                # recolouredImage[length][width] = colourArrayIn[length][width][:]
                recolouredImage[length][width] = recolourPixel2(gradientList[length][width], [100,15,15])[:]
            elif (colourList[length][width] == "N"):
                recolouredImage[length][width] = greyArrayIn[length][width][:]
            else:
                recolouredImage[length][width] = colourArrayIn[length][width][:]
                
    outputList = []

    for length in range(0,lengthIn):
        outputListlayer = []
        for width in range(0,widthIn):
            outputListlayer.append(list(recolouredImage[length][width]))
        outputList.append(outputListlayer)
            
    return outputList

def colourImage(greyArrayInput, colourArrayInput, colourArrayBaseInput, inputRGB, colourType):
    """
    This algorithm uses the grey image input as a golour gradient chart,
    The red image input as a location indicator and the input rgb as 
    the desired colour.
    
    Parameters:
        greyArrayInput (list): 3d list of image rgb values
        redArrayInput (list): 3d list of image rgb values
        inputRGB (list): 1d list of the [r,g,b] values
    """
    lengthImage = len(greyArrayInput)
    widthImage = len(greyArrayInput[0])

    gradientPerMap = determineGardient(greyArrayInput, widthImage, lengthImage)[:]
    colourMap = determineColour(colourArrayInput, widthImage, lengthImage)[:]
    
    outputImage = imageRecolour(colourType, colourMap, gradientPerMap, widthImage, lengthImage, inputRGB, greyArrayInput, colourArrayBaseInput)
    
    return outputImage

def createChapter(rgbIn):
    try:
        # for i in range(5,6,1):
        for i in range(len(filelistCC)):
            print("Generating recolour of", filelistACC[i])
            colourImageExtract = np.asarray(Image.open(filePathCC + filelistCC[i]).convert('RGB'), dtype=np.uint64)
            greyImageExtract = np.asarray(Image.open(filePathA + filelistA[i]).convert('RGB'), dtype=np.uint64)
            colourImageBaseExtract = np.asarray(Image.open(filePathACC + filelistACC[i]).convert('RGB'), dtype=np.uint64)

            newImage = np.array(colourImage(greyImageExtract, colourImageExtract, colourImageBaseExtract, rgbIn, "R"), dtype= np.uint8)   

            im = Image.fromarray(newImage)
            im.save(filePathOUT + filelistA[i][:-6] + ".png")
            
    except Exception as e:
        print(f"Error colouring file: {e}")
    
salamanderGreen = [0,70,30]
salamanderGreenLight = [10, 100, 30]
ultraBlue = [114, 147, 232]
imperialFist = [249, 190, 33]
bloodAngel = [154, 17, 22]

decalColourLight = [220, 220, 220]
decalColourDark = [20, 20, 20]

createChapter(decalColourDark)

# print(recolourPixel(determineGardient([[[223,223,223]]],1,1)[0][0], imperialFist))
# print(determineGardient([[[223,223,223]]],1,1))


# greyImageExtract = np.asarray(Image.open("ch_soldier_shoulders_01_a.png").convert('RGB'))
# colourImageExtract = np.asarray(Image.open("ch_soldier_shoulders_01_cc.png").convert('RGB'))
# colourImage2Extract = np.asarray(Image.open("ch_soldier_shoulders_01_a.png").convert('RGB'))

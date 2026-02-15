import numpy as np
from PIL import Image

RESOLUTION = 10000

def extractImage(pathName):
    """
    This function extracts the specified image from the selected folder and returns an
    RGB array of its colour values.
    
    Args:
        type (str): type specifier, whether the image is a base, grey or mask image 
        position (int): position of the image in the specified file list

    Returns:
        imageArray: a 3D np array of all the rgb values of the image
    """

    imageData = Image.open(pathName).convert('RGB')
    imageArray = np.asarray(imageData, dtype=np.uint64)
    
    return imageArray

def imageRecolour(gradientListIn, maskInputIn, colourArrayIn, inputRGB, widthIn, lengthIn):
    """
    This function takes a grey scale image and calculated a single % value of how light that pixel is.
    This result is stored in a 2D list that is then returned, with each value representing a pixel
    
    &
    
    This function takes a coloured image and determine which pixel is 
    predominantly red, green or blue, based on the highest value in each pixel rgb.
    It then assigns r, g or b to that pixel

    Args:
        gradientInput (3D list): 3D list of the rgb values of the greyscale image
        maskInput (3D list): 3D list of the rgb values of the colour image
        widthIn (int): The width of the image
        lengthIn (int): The length of the image

    Returns:
        3D list: a list containing the new recoloured images as pixels
    """
    
    recolouredImage = np.array([[[0,0,0]]*widthIn]*lengthIn, dtype=np.uint64)

    for length in range(0,lengthIn):
        for width in range(0,widthIn):
            totalColour = gradientListIn[length][width][0] + gradientListIn[length][width][1] + gradientListIn[length][width][2]
            gradientColour = (totalColour / 765) * RESOLUTION
            
            black = maskInputIn[length][width][0] + maskInputIn[length][width][1] + maskInputIn[length][width][2]

            determinedColour = "R"
            
            if (black == 0):
                determinedColour = "N"
            elif (black == 765):
                determinedColour = "W"
            elif (maskInputIn[length][width][0] >= maskInputIn[length][width][1]) and (maskInputIn[length][width][0] >= maskInputIn[length][width][2]):
                determinedColour = "R"
            elif (maskInputIn[length][width][1] >= maskInputIn[length][width][0]) and (maskInputIn[length][width][1] >= maskInputIn[length][width][2]):
                determinedColour = "G"
            elif (maskInputIn[length][width][2] >= maskInputIn[length][width][0]) and (maskInputIn[length][width][2] >= maskInputIn[length][width][1]):
                determinedColour = "B"
            else:
                determinedColour = "R"
                
            if (determinedColour == "R"):
                recolouredImage[length][width] = recolourPixel(gradientColour, inputRGB, gradientListIn[length][width])[:]
                # recolouredImage[length][width] = recolourPixel(gradientColour, decalColourDark)[:]
                # recolouredImage[length][width] = recolourPixelTrims(gradientColour, decalColourLight)[:]
                # recolouredImage[length][width] = colourArrayIn[length][width][:]
            elif (determinedColour == "W"):
                recolouredImage[length][width] = recolourPixelLogo(gradientColour, [145,15,15], gradientListIn[length][width])[:]
            elif (determinedColour == "G"):
                recolouredImage[length][width] = recolourPixelLogo(gradientColour, decalColourLight, gradientListIn[length][width])[:]
                # recolouredImage[length][width] = recolourPixel(gradientColour, decalColourDark)[:]
            elif (determinedColour == "B"):
                recolouredImage[length][width] = recolourPixelTrims(gradientColour, MetalColourGold, gradientListIn[length][width])[:]
                # recolouredImage[length][width] = recolourPixel(gradientColour, decalColourLight, gradientListIn[length][width])[:]
                # recolouredImage[length][width] = recolourPixel(gradientColour, decalColourDark)[:]
                # recolouredImage[length][width] = colourArrayIn[length][width][:]
                # recolouredImage[length][width] = recolourPixelLogo(gradientColour, [100,15,15])[:]
            elif (determinedColour == "N"):
                recolouredImage[length][width] = colourArrayIn[length][width][:]
                # recolouredImage[length][width] = gradientListIn[length][width][:] # Make the colour just be the one from the grey texture
            else:
                recolouredImage[length][width] = colourArrayIn[length][width][:] # Make the colour just be the one from the unedited colour texture
        
    outputList = []

    for length in range(0,lengthIn):
        outputListlayer = []
        for width in range(0,widthIn):
            outputListlayer.append(list(recolouredImage[length][width]))
        outputList.append(outputListlayer)

    return outputList

def recolourPixel(brightness, inputColour, greyColour):
    """
        This function takes an imput colour an scales its brightness.
    Args:
        brightness (float): how close the pixel is to being white
        inputColour (list): rgb colour being scaled

    Returns:
        list: rgb list of scaled colour
    """
    
    # This is done as the darker a colour is, the more it should match the input colour 
    invertPercentage = (RESOLUTION - brightness)/RESOLUTION
    percentage = (brightness)/RESOLUTION
    
    outputColour = [0,0,0]
    
    outputColour[0] = round(inputColour[0] * (invertPercentage))
    outputColour[1] = round(inputColour[1] * (invertPercentage))
    outputColour[2] = round(inputColour[2] * (invertPercentage))
        
    if sum(outputColour) < 150:
        outputColour[0] = round(inputColour[0] * (percentage))    
        outputColour[1] = round(inputColour[1] * (percentage))   
        outputColour[2] = round(inputColour[2] * (percentage))    
    
    # Ultra marine settings
    # if sum(outputColour) < 50:
    #     outputColour[0] = (outputColour[0] + (4 * 6))    
    #     outputColour[1] = (outputColour[1] + (6 * 6))    
    #     outputColour[2] = (outputColour[2] + (10 * 6))   
    # if sum(outputColour) < 100:
    #     outputColour[0] = (outputColour[0] + (4 * 4))    
    #     outputColour[1] = (outputColour[1] + (6 * 4))    
    #     outputColour[2] = (outputColour[2] + (10 * 4))   
    # if sum(outputColour) < 150:
    #     outputColour[0] = (outputColour[0] + (4 * 3))    
    #     outputColour[1] = (outputColour[1] + (6 * 3))    
    #     outputColour[2] = (outputColour[2] + (10 * 3))   
    # if sum(outputColour) < 200:
    #     outputColour[0] = (outputColour[0] + (4 * 2))    
    #     outputColour[1] = (outputColour[1] + (6 * 2))    
    #     outputColour[2] = (outputColour[2] + (10 * 2))   

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
    # if sum(outputColour) < 10:
    #     outputColour[0] = (outputColour[0] + 0)    
    #     outputColour[1] = (outputColour[1] + 0)   
    #     outputColour[2] = (outputColour[2] + 0)    
    # elif sum(outputColour) < 20:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 1) * 1
    # elif sum(outputColour) < 30:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 1) * 1
    # elif sum(outputColour) < 160:
    #     for i in range(3):
    #         outputColour[i] = (outputColour[i] + 1) * 1

    return outputColour

def recolourPixelTrims(brightness, inputColour, greyColour):
    """
        This function takes an imput colour an scales its brightness.
    Args:
        brightness (float): how close the pixel is to being white
        inputColour (list): rgb colour being scaled

    Returns:
        list: rgb list of scaled colour
    """
    
    # This is done as the darker a colour is, the more it should match the input colour 
    invertPercentage = (10000 - brightness)/10000
    percentage = (brightness)/RESOLUTION
    outputColour = [0,0,0]
    
    outputColour[0] = round(inputColour[0] * (invertPercentage))
    outputColour[1] = round(inputColour[1] * (invertPercentage))
    outputColour[2] = round(inputColour[2] * (invertPercentage))

    #-----------------------------------------------------
    # Gold Trims
    # if sum(outputColour) < 100:
    #     outputColour[0] = (outputColour[0] + (25 * 4))    
    #     outputColour[1] = (outputColour[1] + (20 * 4))    
    #     outputColour[2] = (outputColour[2] + (14 * 4))   
    # if sum(outputColour) < 200:
    #     outputColour[0] = (outputColour[0] + (25 * 4))    
    #     outputColour[1] = (outputColour[1] + (20 * 4))    
    #     outputColour[2] = (outputColour[2] + (14 * 4))   
    # if sum(outputColour) < 300:
    #     outputColour[0] = (outputColour[0] + (25 * 3))    
    #     outputColour[1] = (outputColour[1] + (20 * 3))    
    #     outputColour[2] = (outputColour[2] + (14 * 3))   
    # if sum(outputColour) < 400:
    #     outputColour[0] = (outputColour[0] + (25 * 2))    
    #     outputColour[1] = (outputColour[1] + (20 * 2))    
    #     outputColour[2] = (outputColour[2] + (14 * 2))   
    # if sum(outputColour) < 500:
    #     outputColour[0] = (outputColour[0] + (25 * 1))    
    #     outputColour[1] = (outputColour[1] + (20 * 1))    
    #     outputColour[2] = (outputColour[2] + (14 * 1))   
    #-----------------------------------------------------


    
    return outputColour

def recolourPixelLogo(brightness, inputColour, greyColour):
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
    percentage = (brightness)/RESOLUTION
    outputColour = [0,0,0]
    
    for i in range(3):
        outputColour[i] = round(inputColour[i] * (invertPercentage/10000))
        
    if sum(outputColour) < 100:
        outputColour[0] = round(inputColour[0] * (percentage))    
        outputColour[1] = round(inputColour[1] * (percentage))   
        outputColour[2] = round(inputColour[2] * (percentage))    
        

    return outputColour


def createRecolour(imagePosistions):
    try:
        index = imagePosistions[0]
        rgbIn = imagePosistions[1]
        baseImage = imagePosistions[2]
        greyImage = imagePosistions[3]
        maskImage = imagePosistions[4]
        output = imagePosistions[5]

        maskImageExtract = extractImage(maskImage)
        baseImageExtract = extractImage(baseImage)
        greyImageExtract = extractImage(greyImage)
        
        lengthImage = len(greyImageExtract)
        widthImage = len(greyImageExtract[0])
        
        newImage = imageRecolour(greyImageExtract, maskImageExtract, baseImageExtract, rgbIn, widthImage, lengthImage)

        # Generate the image
        imageArr = np.array(newImage, dtype= np.uint8)
        im = Image.fromarray(imageArr)
        nameStart = str(baseImage).rfind('\\') + 1
        im.save(output + baseImage[nameStart:-4] + ".png")
        
        print("Image generated: ", baseImage[nameStart:-4] + ".png")

    except Exception as e:
        print(f"Error colouring file: {e}")
    
decalColourLight = [220, 220, 220]
decalColourDark = [20, 20, 20]
decalColourRed = [145,15,15]
MetalColourRed = [100,15,15]
MetalColourGold1= [255, 204, 143]
MetalColourGold= [215, 164, 103]
MetalColourGold2 = [186, 149, 104]
import os
import multiprocessing
import FileHandler as File
import ColourHandler
import warnings

warnings.filterwarnings("ignore")

salamanderGreen = [0,70,30]
salamanderGreenLight = [10, 100, 30]
# ultraBlue = [114, 147, 232] # More accurate
ultraBlue = [75, 94, 145] # More accurate
imperialFist = [249, 190, 33]
bloodAngel = [154, 17, 22]

decalColourLight = [220, 220, 220]
decalColourDark = [20, 20, 20]

NUM_PROCESSORS = 6
CHAPTER_COLOUR = ultraBlue


if __name__ == "__main__":

    # Create an object for the filehandler file the determines absolute file path
    pathAbs = os.path.abspath(os.getcwd())
    imageFiles = File.FileHandler(pathAbs)

    # populate the list of files with a one time process to find all the files inside the texture folders
    imageFiles.fileListBase = imageFiles.findFiles(imageFiles.filePathBase)
    imageFiles.fileListGrey = imageFiles.findFiles(imageFiles.filePathGrey)
    imageFiles.fileListMask = imageFiles.findFiles(imageFiles.filePathMask)

    numImages = len(imageFiles.fileListBase)

    # Creat a list that has the index, new colour and files that need to be processed
    imagePosistions = [
        [
            i,
            CHAPTER_COLOUR,
            imageFiles.filePathBase + imageFiles.fileListBase[i],
            imageFiles.filePathGrey + imageFiles.fileListGrey[i],
            imageFiles.filePathMask + imageFiles.fileListMask[i],
            imageFiles.filePathOUT,
        ]
        for i in range(numImages)
    ]

    with multiprocessing.Pool(NUM_PROCESSORS) as pool:
        pool.map(ColourHandler.createRecolour, imagePosistions)

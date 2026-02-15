import os

# File handler class
class FileHandler:
    def __init__(self, pathAbs):
        self.pathAbs = pathAbs

        self.fileListBase = []
        self.fileListGrey = []
        self.fileListMask = []

        # File paths for where the images are stored and exported
        self.filePathBase = self.pathAbs + "\Textures_Base\\"
        self.filePathGrey = self.pathAbs + "\Textures_Grey\\"
        self.filePathMask = self.pathAbs + "\Textures_Mask\\"
        self.filePathOUT = self.pathAbs + "\output\\"

    def findFiles(self, filePath):
        fileList = []
        
        for root, dirs, files in os.walk(filePath):
            for file in files:
                # Append the file name to the list
                fileList.append(file)
        
        return fileList
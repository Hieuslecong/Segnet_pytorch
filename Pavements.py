from torch.utils.data import Dataset
from skimage import io
from torchmetrics.functional import jaccard_index, precision, recall, stat_scores
import torch
import os
import time
import numpy as np
import torchvision.transforms as transforms
from skimage.transform import resize
from skimage.color import rgb2gray
import cv2
class Pavements(Dataset):

    def __init__(self, raw_dir, lbl_dir, transform=None):

        # raw_dir: (directory) Folder directory of raw input image files
        # lbl_dir: (directory) Folder directory of labeled image files

        self.raw_dir = raw_dir
        self.lbl_dir = lbl_dir
        self.transform = transform
        self.list_img = [f for f in os.listdir(self.raw_dir) if not f.startswith('.')]
        self.pixel_value_threshold = 127 # Threshold to determine if a pixel belongs to class 0 or 1

    def one_Hot(self, image):
        
        # Used for pixel-wise conversion of labeled images to its respective classes
        # Output is a one-hot encoded tensor of (M, N, 2) dimensions, MxN resolution, 2 channels (classes)
        # For annotated images, assumed that they are monochrome, and white pixels are cracks, while black pixels are anything else

        output_shape = (image.shape[0], image.shape[1], 2)
        output = np.zeros(output_shape)

        # Threshold pixels such that (<= threshold is pavement surface) & (> threshold is pavement crack)
        output[image <= self.pixel_value_threshold, 0] = 1
        output[image > self.pixel_value_threshold, 1] = 1

        return output

    def classify(self, image):
        output = np.zeros_like(image, dtype=np.int)

        # Threshold pixels such that (<= threshold is pavement surface) & (> threshold is pavement crack)
        output[image <= self.pixel_value_threshold] = 0
        output[image > self.pixel_value_threshold] = 1

        return output


    def __len__(self):

        return len(self.list_img)

    def __getitem__(self, idx):
        

        name_img =  (os.path.split(self.list_img[idx])[-1]).split(".")[0]
        name_mask = name_img.split("img")[0] + 'msk'+ name_img.split("img")[1]
        img_name = (os.path.split(self.list_img[idx])[-1]).split(".")[0]
        img_raw_dir = os.path.join(self.raw_dir, img_name+'.jpg')
        #img_lbl_dir = os.path.join(self.lbl_dir, name_img+'.png')
        img_lbl_dir = os.path.join(self.lbl_dir, name_mask+'.png')
        image_raw = io.imread(img_raw_dir)
        image_label = io.imread(img_lbl_dir)
        # image_label=rgb2gray(image_label)
        # image_label[image_label>0]=255
        # a=256
        
        # image_raw=resize(image_raw,(a,a,3))
        # image_label=resize(image_label,(a,a,3))
        #print(image_raw.shape)
        #print(image_label.shape)
        label = self.classify(image_label)

        if self.transform:
            image_raw = self.transform(image_raw)
            label = self.transform(label)

        # create toTensor transform to convert input & label from H x W x C (numpy) to C x H x W (PyTorch)
        to_tensor = transforms.ToTensor()

        data = (to_tensor(image_raw), label)

        return data
    
    def compute_pavement_crack_area(self, pred, as_ratio=False):
      crack_pixels = torch.where(pred == 1.0)[0].shape[0]
      if as_ratio:
        total_pixels = pred.nelement()
        return crack_pixels / total_pixels
      
      return crack_pixels

    def compute_precision(self, pred, target, threshold=0.5):
        # Precision: TP / (TP + FP)

        return precision(pred, target, average='none', mdmc_average='samplewise', ignore_index=None, 
            num_classes=2, threshold=0.5, top_k=None, multiclass=None)

    def compute_recall(self, pred, target, threshold=0.5):
        # Recall: TP / (TP + FN)

        return recall(pred, target, average='none', mdmc_average='samplewise', ignore_index=None, 
            num_classes=2, threshold=0.5, top_k=None, multiclass=None)

    def compute_m_iou(self, pred, target, threshold=0.5):
        # Mean Intersection over Union (mIoU) a.k.a. Jaccard Index

        return jaccard_index(pred, target, 2, ignore_index=None, absent_score=0.0, 
            threshold=threshold, average='none')

    def compute_balanced_class_accuracy(self, pred, target):
        """
          Balanced class accuracy = (Sensitivity + Specificity) / 2
                                  = ((TP / (TP + FN)) + TN / (TN + FP)) / 2
        """
        scores = stat_scores(pred, target, reduce='macro', num_classes=2,
            mdmc_reduce='samplewise') # [[[tp, fp, tn, fn, sup]]]

        tp = scores[:, :, 0]
        fp = scores[:, :, 1]
        tn = scores[:, :, 2]
        fn = scores[:, :, 3]
        sensitivity = tp / (tp + fn)
        specificity = tn / (tn + fp)

        return torch.mean((sensitivity + specificity) / 2, dim=0)[0]

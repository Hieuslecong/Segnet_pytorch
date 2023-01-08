from SegNet import SegNet
from Pavements import Pavements
from datetime import datetime
from torch.utils.tensorboard import SummaryWriter
import torch
import torch.nn as nn
import torch.optim as optim
import argparse
import os
import numpy as np
import json
from torchvision.utils import save_image

def save_checkpoint(state, path):
    torch.save(state, path)
    print("Checkpoint saved at {}".format(path))


def load_model_json():

    # batch_size: Training batch-size
    # epochs: No. of epochs to run
    # lr: Optimizer learning rate
    # momentum: SGD momentum
    # no_cuda: Disables CUDA training (**To be implemented)
    # seed: Random seed
    # in-chn: Input image channels (3 for RGB, 4 for RGB-A)
    # out-chn: Output channels/semantic classes (2 for Pavements dataset)

    with open(os.path.join(os.getcwd(), 'model.json')) as f:
        model_json = json.load(f)

    return model_json


def main(args):

    cuda_available = torch.cuda.is_available()
    writer = SummaryWriter(args.tensorboard_logs_dir)

    weight_fn = args.weight_fn
    model_json = load_model_json()

    assert len(model_json['cross_entropy_loss_weights']) == model_json['out_chn'], "CrossEntropyLoss class weights must be same as no. of output channels"

    trainset = Pavements(args.pavements_raw_dir, args.pavements_labelled_dir)
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=model_json['batch_size'], shuffle=True, num_workers=4)

    model = SegNet(in_chn=model_json['in_chn'], out_chn=model_json['out_chn'], BN_momentum=model_json['bn_momentum'])
    optimizer = optim.SGD(model.parameters(), lr=model_json['learning_rate'], momentum=model_json['sgd_momentum'])
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(model_json['cross_entropy_loss_weights']))

    if cuda_available:
      model.cuda()
      loss_fn.cuda()

    run_epoch = model_json['epochs']
    epoch = None
    if weight_fn is not None:
        if os.path.isfile(weight_fn):
            print("Loading checkpoint '{}'".format(weight_fn))
            checkpoint = torch.load(weight_fn)
            epoch = checkpoint['epoch']
            model.load_state_dict(checkpoint['state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer'])
            print("Loaded checkpoint '{}' (epoch {})".format(weight_fn, checkpoint['epoch']))
        else:
            print("No checkpoint found at '{}'. Will create new checkpoint.".format(weight_fn))
    else:
        print("Starting new checkpoint.".format(weight_fn))
        weight_fn = os.path.join(os.getcwd(), "weights/checkpoint_pavements_{}.pth.tar".format(datetime.now().strftime("%Y%m%d_%H%M%S")))

    for i in range(epoch + 1 if epoch is not None else 1, run_epoch + 1):
        print('Epoch {}:'.format(i))
        sum_loss = 0.0

        for j, data in enumerate(trainloader, 1):
            images, labels = data
            if cuda_available:
              images = images.cuda()
              labels = labels.cuda()
            optimizer.zero_grad()
            output = model(images)
            #images.shape #torch.Size([64,3,28,28])
            img1 = output #torch.Size([3,28,28]
# img1 = img1.numpy() # TypeError: tensor or list of tensors expected, got <class 'numpy.ndarray'>
            save_image(img1, 'img1.png')
            loss = loss_fn(output, labels)
            loss.backward()
            optimizer.step()

            writer.add_scalar('Loss',loss.item()/trainloader.batch_size, j)
            sum_loss += loss.item()

            print('Loss at {} mini-batch: {}'.format(j, loss.item() / trainloader.batch_size))

        print('Average loss @ epoch: {}'.format((sum_loss / (j * trainloader.batch_size))))

    print("Training complete. Saving checkpoint...")
    save_checkpoint({'epoch': run_epoch, 'state_dict': model.state_dict(), 'optimizer' : optimizer.state_dict()}, weight_fn)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    #FORMAT DIRECTORIES
    parser.add_argument("pavements_raw_dir", type=str, help="Directory: Pavements raw training images")
    parser.add_argument("pavements_labelled_dir", type=str, help="Directory: Pavements annotated training images")
    parser.add_argument("tensorboard_logs_dir", type=str, help="Directory: Logs for tensorboard")
    parser.add_argument("--weight-fn", type=str, help="Path: Trained weights", default=None)

    args = parser.parse_args()

    main(args)
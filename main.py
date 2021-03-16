import  torch
import  torch.nn as nn
import  torch.nn.functional as F
import  torch.optim as optim
from    torchvision import datasets, transforms
import torch.backends.cudnn as cudnn
import numpy as np
import os
import argparse
from torch.autograd import Variable
import myNet

from dpwa.application import DpwaApplication

# 端口设置
parser = argparse.ArgumentParser(description='Port design')
parser.add_argument('-myPort', default=9999, type=int, help='myPort')
parser.add_argument('-peerPort', default=9999, type=int, help='peerPort')
parser.add_argument('-name',type=str,help='worker name')

args = parser.parse_args()
myPort=args.myPort
peerPort=args.peerPort
name=args.name


batch_size=200
learning_rate=0.01
# epochs=10


# 准备MNIST数据集

train_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data', train=True, download=True,
                   transform=transforms.Compose([
                       transforms.ToTensor(),
                       # transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=batch_size, shuffle=True)
test_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data', train=False, transform=transforms.Compose([
        transforms.ToTensor(),
        # transforms.Normalize((0.1307,), (0.3081,))
    ])),
    batch_size=batch_size, shuffle=True)


print('MNIST 数据集已经准备完成 !!!')
print('==============MNIST 数据集信息============')
print('训练集====>',train_loader.dataset.data.shape)
print('测试集====>',test_loader.dataset.data.shape)


net = myNet.MLP()

# 检查是GPU是否可用, 并不是特别清楚原理
use_cuda = torch.cuda.is_available()
print(use_cuda)
if use_cuda:
    print('GPU 可用...')
    net.cuda()
    net = torch.nn.DataParallel(net, device_ids=range(torch.cuda.device_count()))
    cudnn.benchmark = True


# #######以下内容使用读取文件的方式获得，此处直接定义###########

config_file = 'dpwa.yaml'
# name = 'w0'

# #######################

# conn = DpwaPyTorchAdapter(net, args.name, args.config_file)
conn=DpwaApplication(net,name,myPort,peerPort)

# 本地训练
criterion = nn.CrossEntropyLoss()
# optimizer = optim.SGD(net.parameters(), lr=args.lr, momentum=0.9, weight_decay=5e-4)  # 优化器在定义的时候就已经传入了网络参数
optimizer = optim.SGD(net.parameters(), lr=learning_rate, momentum=0.9, weight_decay=5e-4) 

MOVING_AVG_SIZE = 10
test_batches=100
best_acc = 0  # best test accuracy
start_epoch = 0  # start from epoch 0 or last checkpoint epoch

def train(Epoch):

    print('\nEpoch: %d' % epoch)
    net.train()
    accuracies = []
    losses = []
    loss_mean = 9999

    #注意，每一次循环取的batch都是随机的
    for batch_idx, (inputs, targets) in enumerate(train_loader):
        if batch_idx > MOVING_AVG_SIZE:
            conn.update_send(loss_mean)

        # inputs.shape = torch.Size([200, 1, 28, 28])  200张图片，1个通道，28*28像素
        # targets.shape = torch.Size([200]) 一维向量, 200个值，对应200张图片的真实结果
        
        inputs = inputs.view(-1, 28*28)  # after view, inputs.shape = torch.Size([200, 784]) 200张图片 28*28=784
        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        optimizer.zero_grad()
        inputs, targets = Variable(inputs), Variable(targets)
        outputs = net(inputs)   # outputs.shape = torch.Size([200, 10]) ,200张图片，每张图片0-9各10个预测值，取最大作为预测结果      
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        losses += [loss.item()]   
        loss_mean = np.array(losses[-MOVING_AVG_SIZE:]).mean()    # 取最近10次loss的均值, losses不足10次则取所有

        if batch_idx > MOVING_AVG_SIZE:
            conn.update_wait(loss_mean)
            
        _, predicted = torch.max(outputs.data, 1)  # outputs.data.shape=torch,size([200,10]), 参数1表示每行取最大, _表示每行的最大值, predicted表示每行最大值的下标,其实就是模型的预测结果
        # predicted.shape=torch.Size([300]), 和targets的size一样
    
        total = targets.size(0) 

        correct = predicted.eq(targets.data).cpu().sum()    # 判断predicted中有多少个预测结果和targets是相等的

        accuracies += [float(correct)/float(total)]
        accuracy = np.array(accuracies[-MOVING_AVG_SIZE:]).mean() * 100.0

        # Show progress
        progress = "[%s] E%d | B%d | Loss: %.3f | Acc: %.3f%%" % \
                   (name, epoch, batch_idx, loss_mean, accuracy)
        print(progress)

        if batch_idx!=0 and batch_idx % test_batches == 0:
           fast_test(epoch)
           net.train()



def fast_test(epoch):
    # global best_acc
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(test_loader):
        inputs = inputs.view(-1, 28*28)
        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        with torch.no_grad():
            inputs, targets = Variable(inputs), Variable(targets)
        outputs = net(inputs)
        loss = criterion(outputs, targets)

        test_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += targets.size(0)
        correct += predicted.eq(targets.data).cpu().sum()
        if batch_idx > test_batches:
           break
        progress = "fast_test...[%s] E%d | B%d | Loss: %.3f | Acc: %.3f%% (%d/%d)" % \
                   (name, epoch, batch_idx, test_loss/(batch_idx+1), 100.*correct/total, correct, total)
        print(progress)
        # LOGGER.info(progress)
        # progress_bar(batch_idx, len(testloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
        #    % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

def test(epoch):
    global best_acc
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(test_loader):
        inputs = inputs.view(-1, 28*28)
        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        
        with torch.no_grad():
            inputs, targets = Variable(inputs), Variable(targets)
        outputs = net(inputs)
        loss = criterion(outputs, targets)

        test_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += targets.size(0)
        correct += predicted.eq(targets.data).cpu().sum()

        progress = "test...[%s] E%d | B%d | Loss: %.3f | Acc: %.3f%% (%d/%d)" % \
                   (name, epoch, batch_idx, test_loss/(batch_idx+1), 100.*correct/total, correct, total)
        print(progress)
        # LOGGER.info(progress)
        # progress_bar(batch_idx, len(testloader), 'Loss: %.3f | Acc: %.3f%% (%d/%d)'
        #    % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

    # Save checkpoint.
    acc = 100.*correct/total
    if acc > best_acc:
        print('Saving..')
        state = {
            'net': net.module if use_cuda else net,
            'acc': acc,
            'epoch': epoch,
        }
        if not os.path.isdir('checkpoint'):
            os.mkdir('checkpoint')
        torch.save(state, 'checkpoint/ckpt.t7')
        best_acc = acc


print('开始训练...')
for epoch in range(start_epoch, start_epoch+10):
    train(epoch)
    test(epoch)

print('训练结束')
import torch
from    torchvision import datasets, transforms

batch_size=200

# 准备MNIST数据集

train_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data2', train=True, download=True,
                   transform=transforms.Compose([
                       transforms.ToTensor(),
                       # transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=batch_size, shuffle=True)
test_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data2', train=False, transform=transforms.Compose([
        transforms.ToTensor(),
        # transforms.Normalize((0.1307,), (0.3081,))
    ])),
    batch_size=batch_size, shuffle=True)


print('MNIST 数据集已经准备完成 !!!')
print('==============MNIST 数据集信息============')
print('训练集====>',train_loader.dataset.data.shape)
print('测试集====>',test_loader.dataset.data.shape)
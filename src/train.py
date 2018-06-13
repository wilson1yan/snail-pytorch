# coding=utf-8
from utils import init_dataset
from omniglot_dataset import OmniglotDataset
from snail import SnailOmniglot

import argparse
import torch
from torch.autograd import Variable
import torch.nn as nn
from torch.optim import Adam
import numpy as np
from tqdm import tqdm
import os
import copy


def init_model(opt):
    if opt.dataset == 'omniglot':
        model = SnailOmniglot(opt.num_cls, opt.num_samples)
    model = model.cuda() if opt.cuda else model
    return model

def save_list_to_file(path, thelist):
    with open(path, 'w') as f:
        for item in thelist:
            f.write("%s\n" % item)

def labels_to_one_hot(opt, labels):
    if opt.cuda:
        labels = labels.cpu()
    labels = labels.numpy()
    unique = np.unique(labels)
    map = {label:idx for idx, label in enumerate(unique)}
    idxs = [map[labels[i]] for i in range(labels.size)]
    one_hot = np.zeros((labels.size, unique.size))
    one_hot[np.arange(labels.size), idxs] = 1
    return one_hot, idxs

def train(opt, tr_dataloader, model, optim, val_dataloader=None):
    if val_dataloader is None:
        best_state = None
    train_loss = []
    train_acc = []
    val_loss = []
    val_acc = []
    best_acc = 0

    best_model_path = os.path.join(opt.exp, 'best_model.pth')
    last_model_path = os.path.join(opt.exp, 'last_model.pth')

    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(opt.epochs):
        print('=== Epoch: {} ==='.format(epoch))
        tr_iter = iter(tr_dataloader)
        model.train()
        model = model.cuda()
        for batch in tqdm(tr_iter):
            optim.zero_grad()
            x, y = batch
            one_hot, idxs = labels_to_one_hot(opt, y)
            last_target = Variable(torch.Tensor(np.array([idxs[-1]])).long())
            y = torch.Tensor(one_hot)
            x, y = Variable(x), Variable(y)
            if opt.cuda:
                x, y = x.cuda(), y.cuda()
                last_target = last_target.cuda()
            model_output = model(x, y)
            last_model = model_output[:, -1, :].view((-1, opt.num_cls))
            loss = loss_fn(last_model, last_target)
            loss.backward()
            optim.step()
            train_loss.append(loss.data[0])
            #train_acc.append(acc.data[0])
        avg_loss = np.mean(train_loss[-opt.iterations:])
        #avg_acc = np.mean(train_acc[-opt.iterations:])
        #print('Avg Train Loss: {}, Avg Train Acc: {}'.format(avg_loss, avg_acc))
        print('Avg Train Loss: {}'.format(avg_loss))
        if val_dataloader is None:
            continue
        val_iter = iter(val_dataloader)
        model.eval()
        for batch in val_iter:
            x, y = batch
            x, y = Variable(x), Variable(y)
            if opt.cuda:
                x, y = x.cuda(), y.cuda()
            model_output = model(x)
            l, acc = loss(model_output, target=y, n_support=opt.num_support_val) 
            val_loss.append(l.data[0])
            val_acc.append(acc.data[0])
        avg_loss = np.mean(val_loss[-opt.iterations:])
        avg_acc = np.mean(val_acc[-opt.iterations:])
        postfix = ' (Best)' if avg_acc >= best_acc else ' (Best: {})'.format(
            best_acc)
        print('Avg Val Loss: {}, Avg Val Acc: {}{}'.format(
            avg_loss, avg_acc, postfix))
        if avg_acc >= best_acc:
            torch.save(model.state_dict(), best_model_path)
            best_acc = avg_acc
            best_state = model.state_dict()

    torch.save(model.state_dict(), last_model_path)

    for name in ['train_loss', 'train_acc', 'val_loss', 'val_acc']:
        save_list_to_file(os.path.join(opt.exp, name + '.txt'), locals()[name])

    return best_state, best_acc, train_loss, train_acc, val_loss, val_acc


def test(opt, test_dataloader, model):
    avg_acc = list()
    for epoch in range(10):
        test_iter = iter(test_dataloader)
        for batch in test_iter:
            x, y = batch
            x, y = Variable(x), Variable(y)
            if opt.cuda:
                x, y = x.cuda(), y.cuda()
            model_output = model(x)
            l, acc = loss(model_output, target=y, n_support=opt.num_support_tr)
            avg_acc.append(acc.data[0])
    avg_acc = np.mean(avg_acc)
    print('Test Acc: {}'.format(avg_acc))

    return avg_acc

def main():
    '''
    Initialize everything and train
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--exp', type=str, default='default')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--dataset', type=str, default='omniglot')
    parser.add_argument('--num_cls', type=int, default=5)
    parser.add_argument('--num_samples', type=int, default=1)
    parser.add_argument('--lr', type=float, default=0.01)
    parser.add_argument('--cuda', action='store_true')
    options = parser.parse_args()

    if not os.path.exists(options.exp):
        os.makedirs(options.exp)

    if torch.cuda.is_available() and not options.cuda:
        print("WARNING: You have a CUDA device, so you should probably run with --cuda")

    tr_dataloader, val_dataloader, trainval_dataloader, test_dataloader = init_dataset(
        options)
    model = init_model(options)
    optim = torch.optim.Adam(params=model.parameters(), lr=options.lr)
    res = train(opt=options,
                tr_dataloader=tr_dataloader,
                val_dataloader=val_dataloader,
                model=model,
                optim=optim)
    best_state, best_acc, train_loss, train_acc, val_loss, val_acc = res
    print('Testing with last model..')
    test(opt=options,
         test_dataloader=test_dataloader,
         model=model)

    model.load_state_dict(best_state)
    print('Testing with best model..')
    test(opt=options,
         test_dataloader=test_dataloader,
         model=model)

if __name__ == '__main__':
    main()

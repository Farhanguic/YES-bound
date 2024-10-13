# -*- coding: utf-8 -*-
"""YES_bound_image_denoising.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1K2RVpegkKAZUeaD8m-ROyQPRSDKgCQJ3
"""

import torch as tc
import torch.nn as nn
import torch.nn.functional as F
#from torch.utils.data import DataLoader
import numpy as np
import matplotlib.pyplot as plt
#from sklearn.model_selection import train_test_split
import torch.optim.lr_scheduler as lr_scheduler
from torch.optim.lr_scheduler import MultiStepLR
from PIL import Image
from torchvision import transforms
from google.colab import drive
import pickle
import copy
import torch.nn.init as init
import time
from IPython.display import clear_output
#from scipy.ndimage import gaussian_filter
#import cv2
# Mount Google Drive
drive.mount('/content/gdrive')

class struct():
    '''
    an empty class to use structure type variable
    '''
    pass

class Fully_model(tc.nn.Module):
    def __init__(self,params):
      super(Fully_model, self).__init__()
      self.K=params.Layers
      m=params.m
      Layers=params.Layers
      self.W=nn.ModuleList([nn.Linear(m,m,bias=params.bias) for _ in range(Layers)])
      #self.batch_norms = nn.ModuleList([nn.BatchNorm1d(m) for _ in range(Layers)])
############################################################################################################################################################
    def forward(self,x):
      per_out=[]
      x_k=x
      for k in range(self.K):
        temp=self.W[k](x_k)
        #x_k=tc.nn.functional.relu(temp)
        if k != self.K-1:
          #temp=self.batch_norms[k](temp)
          x_k=tc.nn.functional.relu(temp)
        else:
          x_k=temp
        per_out.append(x_k)
      return  x_k,per_out
############################################################################################################################################################
def extract_patches(image, patch_size, stride):
    """
    Extract overlapping patches from a 2D image.
    :param image: Input image as a 2D PyTorch tensor (1, m, n).
    :param patch_size: Size of the patches (e.g., 8 for 8x8 patches).
    :param stride: Stride or step size for patch extraction.
    :return: Extracted patches as a tensor of shape (num_patches, patch_size, patch_size).
    """
    patches = []
    img_h, img_w = image.shape[1], image.shape[2]

    for i in range(0, img_h - patch_size + 1, stride):
        for j in range(0, img_w - patch_size + 1, stride):
            patch = image[:, i:i + patch_size, j:j + patch_size]
            patches.append(patch)

    patches = tc.cat(patches, dim=0)  # Concatenate along the batch dimension
    return patches
############################################################################################################################################################
def reconstruct_image(input_tensor, img_h, img_w, patch_size, stride, num_noise, total_patch_number):
    """
    Reconstruct the image from patches by averaging overlapping pixels.
    :param patches: Patches as a tensor of shape (num_patches, 1, patch_size, patch_size).
    :param img_h: Height of the original image.
    :param img_w: Width of the original image.
    :param patch_size: Size of the patches (e.g., 8 for 8x8 patches).
    :param stride: Stride or step size for patch extraction.
    :return: Reconstructed image as a 2D PyTorch tensor.
    """
    input_tensor_t = input_tensor.transpose(0,1)
    tensor_rec = tc.zeros((total_patch_number, patch_size * patch_size), dtype = tc.float32)
    for i in range(total_patch_number):
      tensor_rec[i,:] = input_tensor_t[i*num_noise]
    patches = tensor_rec.view(total_patch_number, patch_size, patch_size)
    # Initialize an empty image and a count matrix for averaging
    reconstructed_img = tc.zeros((1, img_h, img_w), dtype=tc.float32)
    patch_count = tc.zeros((1, img_h, img_w), dtype=tc.float32)

    patch_idx = 0
    for i in range(0, img_h - patch_size + 1, stride):
        for j in range(0, img_w - patch_size + 1, stride):
            reconstructed_img[:, i:i + patch_size, j:j + patch_size] += patches[patch_idx]
            patch_count[:, i:i + patch_size, j:j + patch_size] += 1
            patch_idx += 1
    # Average the overlapping pixels
    reconstructed_img /= patch_count
    reconstructed_img = reconstructed_img.squeeze(0)
    return reconstructed_img
############################################################################################################################################################
def train(model,params):
   n_img=params.n_img
   patch_size=params.patch_size
   num_noise=params.num_noise
   total_patch_number = params.total_patch_number
   stride=params.stride
   whole_dataset_size=params.whole_dataset_size
   m=params.m
   BATCH_SIZE=params.BATCH_SIZE
   NUM_BATCH=int(whole_dataset_size/BATCH_SIZE)
   NUM_EPOCHS=params.NUM_EPOCHS
   Layers=params.Layers
   X=params.Xdata
   Y=params.Ydata
   noisy_img=reconstruct_image(X, n_img, n_img, patch_size, stride, num_noise, total_patch_number)
   original_img=reconstruct_image(Y, n_img, n_img, patch_size, stride, num_noise, total_patch_number)
   X_train=X.transpose(0,1)
   Y_train=Y.transpose(0,1)
   bias_cond=params.bias
   # computing YES-0 bound for training
   if not bias_cond:
    # with no bias
    W_k=tc.matmul(Y,tc.linalg.pinv(X))
    Y_k=tc.nn.functional.relu(tc.matmul(W_k,X))
    for k in range(Layers-1):
      W_k=tc.matmul(Y,tc.linalg.pinv(Y_k))
      if k != Layers-2:
        Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_k))
      else:
        Y_k=tc.matmul(W_k,Y_k)
        #Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_k))
   else:
    # with bias
    Y_k=X
    for k in range(Layers):
      Y_t=tc.vstack((Y_k, tc.ones(1,whole_dataset_size)))
      W_k=tc.matmul(Y,tc.linalg.pinv(Y_t))
      if k != Layers-1:
        Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_t))
      else:
        Y_k=tc.matmul(W_k,Y_t)
        #Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_t))
   s=0
   for i in range(whole_dataset_size):
    s+=(tc.norm(Y_k[:,i]-Y[:,i])**2)
   s=s/whole_dataset_size
   Y_0=Y_k
   YES_0_bound=tc.tensor([s])
   report=struct()
   criterion=tc.nn.MSELoss(reduction='sum') # square error loss
   optimizer=tc.optim.Adam(model.parameters(),lr=params.lr)
   if params.schedule:
    scheduler=lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.9)
   train_loss_ep=[]
   YES_k_bounds=tc.zeros((Layers-1,NUM_EPOCHS), dtype = tc.float32)
   # Define colors
   spring_green = "#00FF7F"  # Bright and vibrant green
   golden_color = "#FFD700"   # Golden color for the yellow area
   pleasant_red = "#FFB6C1"   # Light pinkish red for the red area
   # determine whether bias of l
   bias_cond=params.bias
   for epoch in range(NUM_EPOCHS):
      j_batch=0
      while j_batch<NUM_BATCH:
           b=X_train[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]
           x=Y_train[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]
           # forward pass
           x_hat,_=model(b)
           loss=criterion(x_hat,x) # our objective function
           # backward pass
           optimizer.zero_grad()
           loss.backward()
           # update
           optimizer.step()
           j_batch+=1
      if params.schedule:
        scheduler.step()
      current_lr = optimizer.param_groups[0]['lr']
      print(f"Epoch {epoch}, Learning Rate: {current_lr}")
      # creating the per-layer output
      with tc.no_grad():
        All_out=[]
        for i in range(Layers):
          wholeData=tc.zeros((whole_dataset_size,m), dtype = tc.float32)
          j_batch=0
          while j_batch<NUM_BATCH:
            b=X_train[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]
            _,per_out=model(b)
            wholeData[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]=per_out[i]
            j_batch+=1
          All_out.append(wholeData)
        Y_training=All_out[Layers-1]
        rec_img=reconstruct_image(Y_training.transpose(0,1), n_img, n_img, patch_size, stride, num_noise, total_patch_number)
        # general code for generating YES-k bounds
        if Layers != 1:
          layer_indces=tc.arange(0,Layers-1)
          for k in range(1,Layers):
            layer_combinations=tc.combinations(layer_indces, r=k)
            temp_k_bound=tc.zeros(layer_combinations.shape[0], dtype = tc.float32)
            for i in range(layer_combinations.shape[0]):
              l=0
              Y_sigma=[]
              for j in range(k):
                Y_sigma.append(All_out[layer_combinations[i][j].item()].transpose(0,1))
              Y_k=X
              for j in range(k):
                while l<=layer_combinations[i][j].item():
                  if not bias_cond:
                    # with no bias
                    W_k=tc.matmul(Y_sigma[j],tc.linalg.pinv(Y_k))
                    Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_k))
                  else:
                    # with bias
                    Y_t=tc.vstack((Y_k, tc.ones(1,whole_dataset_size)))
                    W_k=tc.matmul(Y_sigma[j],tc.linalg.pinv(Y_t))
                    Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_t))
                  l+=1
              for cnt in range(Layers-l):
                if not bias_cond:
                  # with no bias
                  W_k=tc.matmul(Y,tc.linalg.pinv(Y_k))
                  if cnt != Layers-l-1:
                    Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_k))
                  else:
                    Y_k=tc.matmul(W_k,Y_k)
                    #Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_k))
                else:
                  # with bias
                  Y_t=tc.vstack((Y_k, tc.ones(1,whole_dataset_size)))
                  W_k=tc.matmul(Y,tc.linalg.pinv(Y_t))
                  if cnt != Layers-l-1:
                    Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_t))
                  else:
                    Y_k=tc.matmul(W_k,Y_t)
                    #Y_k=tc.nn.functional.relu(tc.matmul(W_k,Y_t))
              s=0
              for h in range(whole_dataset_size):
                s+=(tc.norm(Y_k[:,h]-Y[:,h])**2)
              s=s/whole_dataset_size
              temp_k_bound[i]=s
            if k==1:
              YES_k_bounds[k-1,epoch]=tc.min(tc.cat((YES_0_bound,temp_k_bound)))
              if (epoch>=1) and (YES_k_bounds[k-1,epoch]-YES_k_bounds[k-1,epoch-1]>0):
                YES_k_bounds[k-1,epoch]=YES_k_bounds[k-1,epoch-1]
            else:
              YES_k_bounds[k-1,epoch]=tc.min(tc.cat((temp_k_bound,tc.tensor([YES_k_bounds[k-2,epoch].item()]))))
              if (epoch>=1) and (YES_k_bounds[k-1,epoch]-YES_k_bounds[k-1,epoch-1]>0):
                YES_k_bounds[k-1,epoch]=YES_k_bounds[k-1,epoch-1]
      if epoch%1==0:
        with tc.no_grad():
          train_loss=0
          j_batch=0
          while j_batch<NUM_BATCH:
            b=X_train[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]
            x=Y_train[BATCH_SIZE*j_batch:BATCH_SIZE*(j_batch+1),:]
            x_hat,_=model(b)
            train_loss+=mse(x_hat,x)
            j_batch+=1
          train_loss=train_loss/whole_dataset_size
          train_loss_ep.append(train_loss.item())
          print('Epoch {}/{}'.format(epoch, NUM_EPOCHS),'Train LOSS: {:.2f}'.format(train_loss.item()),'|| {:.2f}'.format(10*np.log10(train_loss.item())),'dB\n')
      # online plot the training dynamics and noisy/reconstructed images
      YES_3_bound=YES_k_bounds[Layers-2,0:epoch+1]
      clear_output(wait=True)
      fig1, ax1 = plt.subplots()
      # Plot the data with different colors and line styles
      ax1.plot([10*np.log10(YES_0_bound.item())] * len(YES_3_bound), color='red', linestyle='-', linewidth=2)
      ax1.plot(10*np.log10(YES_3_bound), color='orange', linestyle='-.', linewidth=2)
      ax1.plot(10*np.log10(train_loss_ep), color='navy', linestyle='-', linewidth=2, label='Training Loss')
      #for i in range(len(YES_3_bound)):
      #  if train_loss_ep[i] < YES_3_bound[i]:
      #    plt.scatter(i, 10*np.log10(train_loss_ep[i]), color='red', marker='o', s=20)
      #
      ymin, ymax = ax1.get_ylim()
      # Set the background color regions using fill_between for non-straight regions
      ax1.fill_between(np.arange(0, len(YES_3_bound), 1), 10*np.log10(YES_0_bound.item()), ymax, facecolor=pleasant_red, alpha=0.4, hatch='xx', edgecolor='red', label='Ineffective Training')
      ax1.fill_between(np.arange(0, len(YES_3_bound), 1), 10*np.log10(YES_3_bound), 10*np.log10(YES_0_bound.item()), facecolor=golden_color, alpha=0.4, hatch='//', edgecolor='gold', label='Caution')
      ax1.fill_between(np.arange(0, len(YES_3_bound), 1), ymin, 10*np.log10(YES_3_bound), facecolor=spring_green, alpha=0.4, label='Effective Training')
      ax1.set_ylabel('MSE(dB)')
      ax1.set_xlabel('Epoch number')
      #plt.legend(loc='center', bbox_to_anchor=(0.75, 0.85))
      ax1.legend(loc='center', bbox_to_anchor=(0.85, 0.8), fontsize='small', borderpad=0.2, labelspacing=0.3)
      ax1.grid(alpha=0.7)
      plt.tight_layout()
      plt.show()
      fig2, ax2 = plt.subplots(1, 3)
      ax2[0].imshow(original_img, cmap='gray', vmin=0, vmax=1)
      ax2[0].set_title('original image')
      ax2[1].imshow(noisy_img, cmap='gray', vmin=0, vmax=1)
      ax2[1].set_title('noisy image')
      ax2[2].imshow(rec_img, cmap='gray', vmin=0, vmax=1)
      ax2[2].set_title('reconstructed image')
      plt.tight_layout()
      plt.show()
      # save figures for four critical points
      if epoch ==0:
        i_yes_0=0
        i_yes_k=0
      if epoch == 0:
        # Create a new figure for the reconstructed image alone
        fig_reconstructed, ax_reconstructed = plt.subplots()
        ax_reconstructed.imshow(rec_img, cmap='gray', vmin=0, vmax=1)
        ax_reconstructed.set_title('reconstructed image')
        ax_reconstructed.axis('off')  # Remove the axis for a cleaner look
        # Save only the reconstructed image
        fig_reconstructed.savefig("/content/gdrive/My Drive/ICLR_2025_YES_bound_paper/rec_fig_initial_boat.png", format="png", bbox_inches='tight')
        plt.close(fig_reconstructed)  # Close the figure to avoid display in future epochs
        time.sleep(10)
        print("10 seconds have passed!")
      if (train_loss<YES_0_bound.item()) and (i_yes_0==0):
        # Create a new figure for the reconstructed image alone
        fig_reconstructed, ax_reconstructed = plt.subplots()
        ax_reconstructed.imshow(rec_img, cmap='gray', vmin=0, vmax=1)
        ax_reconstructed.set_title('reconstructed image')
        ax_reconstructed.axis('off')  # Remove the axis for a cleaner look
        # Save only the reconstructed image
        fig_reconstructed.savefig("/content/gdrive/My Drive/ICLR_2025_YES_bound_paper/rec_fig_below_YES_0_boat.png", format="png", bbox_inches='tight')
        plt.close(fig_reconstructed)  # Close the figure to avoid display in future epochs
        i_yes_0=1
        time.sleep(10)
        print("10 seconds have passed!")
      if (train_loss<YES_3_bound[-1].item()) and (i_yes_k==0):
        # Create a new figure for the reconstructed image alone
        fig_reconstructed, ax_reconstructed = plt.subplots()
        ax_reconstructed.imshow(rec_img, cmap='gray', vmin=0, vmax=1)
        ax_reconstructed.set_title('reconstructed image')
        ax_reconstructed.axis('off')  # Remove the axis for a cleaner look
        # Save only the reconstructed image
        fig_reconstructed.savefig("/content/gdrive/My Drive/ICLR_2025_YES_bound_paper/rec_fig_below_YES_K_boat.png", format="png", bbox_inches='tight')
        plt.close(fig_reconstructed)  # Close the figure to avoid display in future epochs
        i_yes_k=1
        time.sleep(10)
        print("10 seconds have passed!")
      if epoch == NUM_EPOCHS-1:
        # Create a new figure for the reconstructed image alone
        fig_reconstructed, ax_reconstructed = plt.subplots()
        ax_reconstructed.imshow(rec_img, cmap='gray', vmin=0, vmax=1)
        ax_reconstructed.set_title('reconstructed image')
        ax_reconstructed.axis('off')  # Remove the axis for a cleaner look
        # Save only the reconstructed image
        fig_reconstructed.savefig("/content/gdrive/My Drive/ICLR_2025_YES_bound_paper/rec_fig_last_epoch_boat.png", format="png", bbox_inches='tight')
        print('it comes to end')
        plt.close(fig_reconstructed)  # Close the figure to avoid display in future epochs
        time.sleep(10)
        print("10 seconds have passed!")
   return  train_loss_ep,YES_0_bound,YES_k_bounds
############################################################################################################################################################
def mse(b, b_star):
  #norm_b_star = tc.norm(b_star, dim=1)**2
  temp=tc.sum((b - b_star)**2,dim=1)
  mse=tc.sum(temp)
  return mse

# load the image
img = Image.open('/content/gdrive/My Drive/cameraman.png').convert('L')
# resize the image to 128x128
n_img = 128
resize_transform = transforms.Resize((n_img, n_img))
img_resized = resize_transform(img)

# transform the image to tensor
transform = transforms.ToTensor()
img_tensor = transform(img_resized)

patch_size = 8
stride = 6
m = patch_size * patch_size
patches = extract_patches(img_tensor, patch_size, stride)
total_patch_number = patches.shape[0]
patches_vectorized = patches.view(total_patch_number, m)

params = struct()
params.n_img=n_img
params.patch_size=patch_size
params.m = m
params.total_patch_number = total_patch_number
params.stride = stride

# creating dataset
params.num_noise = 10
num_noise = params.num_noise
params.whole_dataset_size = num_noise * patches.shape[0]
whole_dataset_size = params.whole_dataset_size
x = tc.zeros((whole_dataset_size, m), dtype = tc.float32)
b = tc.zeros((whole_dataset_size, m), dtype = tc.float32)
A = tc.normal(0, np.sqrt(1/m), (m, m))
i = 0
j = 0
while i<whole_dataset_size:
  for _ in range(num_noise):
    x[i]=patches_vectorized[j]
    n=tc.normal(0, 0.1, size=(m,1)).squeeze(1)
    #b[i]=x[i]*n
    b[i]=tc.abs(tc.matmul(A,x[i]))**2+n
    #b[i]=tc.matmul(A,x[i])+n
    i+=1
  j+=1
X=b.transpose(0,1)
Y=x.transpose(0,1)
params.Xdata=X
params.Ydata=Y
print(whole_dataset_size)

params.Layers      = 5
params.BATCH_SIZE  = 90
params.NUM_EPOCHS  = 1000
params.lr          = 1e-3   # 1e-3 is  best
params.bias        = True
params.schedule    = True

model=Fully_model(params)
params.train_loss,params.YES_0_bound,params.YES_k_bounds=train(model,params)

YES_0_bound=params.YES_0_bound
YES_3_bound=params.YES_k_bounds[params.Layers-2,:]
#YES_3_bound=YES_3_bound.tolist()

train_loss=params.train_loss
#zoom_up = 200
zoom_up = params.NUM_EPOCHS
zoom_indices = np.arange(0, zoom_up)
YES_3_bound_box = YES_3_bound[zoom_indices]
train_loss_box = train_loss[0:zoom_up]
fig, ax = plt.subplots()
# Define colors
spring_green = "#00FF7F"  # Bright and vibrant green
golden_color = "#FFD700"  # Golden color for the yellow area
pleasant_red = "#FFB6C1"  # Light pinkish red for the red area
# Plot the data with different colors and line styles
plt.plot(np.arange(0, zoom_up, 1), [10*np.log10(YES_0_bound.item())] * zoom_up,
         color='red', linestyle='-', linewidth=2, label='YES-0 Training Bound')
plt.plot(np.arange(0, zoom_up, 1), 10*np.log10(YES_3_bound_box),
         color='green', linestyle='--', linewidth=2, label='YES-4 Training Bound')
plt.plot(np.arange(0, zoom_up, 1), 10*np.log10(train_loss_box),
         color='navy', linestyle='-', linewidth=2, label='Training Loss')
# get the y-axis limits
ymin, ymax = ax.get_ylim()
# Set the background color regions using fill_between for non-straight regions
plt.fill_between(np.arange(0, zoom_up, 1), 10*np.log10(YES_0_bound.item()), ymax, facecolor=pleasant_red, alpha=0.4, hatch='xx', edgecolor='red', label='Ineffective Training')
plt.fill_between(np.arange(0, zoom_up, 1), 10*np.log10(YES_3_bound_box), 10*np.log10(YES_0_bound.item()), facecolor=golden_color, alpha=0.4, hatch='//', edgecolor='gold', label='YES Cloud (Caution)')
plt.fill_between(np.arange(0, zoom_up, 1), ymin, 10*np.log10(YES_3_bound_box), facecolor=spring_green, alpha=0.4, label='Effective Training')
###
plt.tight_layout()
plt.ylabel('MSE(dB)',fontsize=13)
plt.xlabel('Epoch Number',fontsize=13)
plt.title('YES Cloud and Training Loss Progression',fontsize=15)
plt.legend(loc='center', bbox_to_anchor=(0.825, 0.78), fontsize='small', borderpad=0.2, labelspacing=0.3)
plt.grid(alpha=0.7)
plt.savefig("/content/gdrive/My Drive/ICLR_2025_YES_bound_paper/fig_cman_cloud_iclr.png", format="png", bbox_inches="tight")
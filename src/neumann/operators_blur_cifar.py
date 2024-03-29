import numpy as np
import torch
from torch import nn


class BlurModel(nn.Module):
    def __init__(self, device, add_noise: bool = False, kernel_size: int = 5, padding: int = 2,
                 channels: int = 3, filter_sigma: float = 0.001):
        super(BlurModel, self).__init__()
        self.device = device
        self.add_noise = add_noise
        filter = nn.Conv2d(in_channels=channels, out_channels=channels,
                           padding=(padding, padding), kernel_size=(kernel_size, kernel_size), groups=channels,
                           bias=False)
        blur_kernel = self.special_gauss(size=kernel_size, sigma=filter_sigma)
        blur_kernel_repeat = blur_kernel.reshape((kernel_size, kernel_size, 1, 1))
        blur_kernel_repeat = np.repeat(blur_kernel_repeat, channels, axis=2)
        blur_kernel_repeat = np.transpose(blur_kernel_repeat, (2, 3, 0, 1))
        blur_kernel = torch.from_numpy(blur_kernel_repeat).float()
        blur_kernel = blur_kernel.to(device)
        filter.weight.data = blur_kernel
        filter.weight.requires_grad = False
        self.filter = filter

    def special_gauss(self, size, sigma):
        x, y = np.mgrid[-size // 2 + 1:size // 2 + 1, -size // 2 + 1:size // 2 + 1]
        g = np.exp(-((x ** 2 + y ** 2) / (2.0 * sigma ** 2)))
        return g / (g.sum())

    def forward(self, input):
        input = input.to(self.device)
        output = self.filter(input)
        return output


class GramianModel(nn.Module):

    def __init__(self, blur_model):
        super(GramianModel, self).__init__()
        self.blur_model = blur_model

    def forward(self, input):
        return self.blur_model(self.blur_model(input))


class CorruptionModel(nn.Module):
    def __init__(self, device, blur_model, mean_noise: float = 0.0, sigma_noise: float = 0.5):
        super(CorruptionModel, self).__init__()
        self.device = device
        self.blur_model = blur_model
        self.normal_dist = torch.distributions.Normal(loc=torch.tensor([mean_noise]), scale=torch.tensor([sigma_noise]))

    def forward(self, input):
        input = input.to(self.device)
        output = self.blur_model(input)
        sample = self.normal_dist.sample((output.view(-1).size())).reshape(output.size()).to(self.device)
        return output.add(sample)

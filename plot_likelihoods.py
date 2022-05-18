#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
plot_likelihoods.py

Generate plots of simulated data, data sampled from the learned
likelihood, a grid of the true likelihood, and a grid of the 
learned likelihood.

Copyright(C) 2020 by Trey Wenger <tvwenger@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Trey Wenger - August 2020
"""

import os
import argparse
import pickle
from torch_prior import Prior
import matplotlib.pyplot as plt
from model.simulator import simulator
from model.likelihood import log_like
import numpy as np
import torch

_THETA = [0.25, 5.0, 0.5, 0.1, 8.166, 10.444, 12.007, 7.719, 5.793,
          -3.562, 0.978, 1.623, 5.5, 0.0, 0.0399, -0.5]

def main(net_fname, num_data=500, theta=_THETA, outdir='frames',
         Rmin=3.0, Rmax=15.0, Rref=8.0):
    """
    Generate plots of simulated data, data sampled from the learned
    likelihood, a grid of the true likelihood, and a grid of the
    learned likelihood for a given set of parameters and varying
    reference azimuth. Each reference azimuth frame is saved to outdir
    with prefix frame_*, and can be combined into a gif with:
    ffmpeg -v 0 -i frame_%03d.png -vf palettegen -y palette.png
    ffmpeg -v 0 -framerate 20 -loop 0 -i frame_%03d.png -i palette.png -lavfi paletteuse -y movie.gif

    Inputs:
      net_fname :: string
        Filename of the neural network pickle file
      num_data :: integer
        Number of simulated and sampled data to draw
      theta :: list of scalars
        Model parameters held fixed:
        pitch, sigmaV, sigma_arm_plane, sigma_arm_height, R0, Usun,
        Vsun, Wsun, Upec, Vpec, a2, a3, Zsun, roll, warp_amp, warp_off
      outdir :: string
        Directory where images are saved
      Rmin, Rmax :: scalars (kpc)
        The minimum and maximum radii of the spirals
      Rref :: scalar (kpc)
        The radius where the arm crosses the reference azimuth

    Returns: Nothing
    """
    #
    # add az0 placeholder to theta. Get range of az0
    #
    theta = torch.tensor([0.0]+theta)
    az0s_deg = np.linspace(0.0, 359.0, 360)
    az0s = np.deg2rad(az0s_deg)
    #
    # Load neural network
    #
    with open(net_fname, 'rb') as f:
        net = pickle.load(f)
    #
    # data grid
    #
    glong_axis = np.linspace(-np.pi, np.pi, 180)
    vlsr_axis = np.linspace(-150.0, 150.0, 150)
    glong_grid, vlsr_grid = np.meshgrid(glong_axis, vlsr_axis, indexing='ij')
    glong = glong_grid.flatten()
    vlsr = vlsr_grid.flatten()
    glat = np.zeros(len(glong))
    extent = [-150.0, 150.0, -180.0, 180.0]
    grid = np.stack((glong, glat, vlsr)).T
    grid = torch.tensor(grid).float()
    #
    # Loop over azimuth
    #
    for i, (az0_deg, az0) in enumerate(zip(az0s_deg, az0s)):
        fig, ax = plt.subplots(
            1, 4, sharex=True, sharey=True, figsize=(16, 9))
        fig.subplots_adjust(
            left=0.075, right=0.99, bottom=0.225, top=0.95, wspace=0)
        theta[0] = az0
        #
        # Simulated data
        #
        data = simulator(
            theta.expand(num_data, -1),
            Rmin=torch.tensor(Rmin), Rmax=torch.tensor(Rmax),
            Rref=torch.tensor(Rref))
        data = data.numpy()
        cax0 = ax[0].scatter(
            data[:, 2], np.rad2deg(data[:, 0]), marker='.',
            c=np.rad2deg(data[:, 1]), vmin=-5.0, vmax=5.0)
        ax[0].set_ylabel('Longitude (deg)')
        ax[0].set_xlabel('VLSR (km/s)')
        ax[0].set_title('Simulated')
        ax[0].set_xlim(-150.0, 150.0)
        ax[0].set_ylim(-180.0, 180.0)
        label = r'$\theta_0 = '+'{0:.1f}'.format(az0_deg)+r'^\circ$'
        props = {'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.5}
        ax[0].text(-100, 150, label, fontsize=24, bbox=props)
        #
        # Sampled data
        #
        data = net['posterior'].net.sample(num_data, context=theta[None])[0]
        data = data.detach().numpy()
        cax1 = ax[1].scatter(
            data[:, 2], np.rad2deg(data[:, 0]), marker='.',
            c=np.rad2deg(data[:, 1]), vmin=-5.0, vmax=5.0)
        ax[1].set_xlabel('VLSR (km/s)')
        ax[1].set_xlim(-150.0, 150.0)
        ax[1].set_ylim(-180.0, 180.0)
        ax[1].set_title('Sampled')
        #
        # Grid true likelihood data
        #
        logp = log_like(
            grid, theta, Rmin=torch.tensor(Rmin),
            Rmax=torch.tensor(Rmax), Rref=torch.tensor(Rref),
            az_bins=1000)
        logp = logp.detach().numpy()
        logp = logp.reshape(glong_grid.shape)
        cax2 = ax[2].imshow(
            logp-logp.max(), extent=extent, origin='lower',
            interpolation='none', vmin=-20.0, vmax=0.0, aspect='auto')
        ax[2].set_xlabel('VLSR (km/s)')
        ax[2].set_xlim(-150.0, 150.0)
        ax[2].set_ylim(-180.0, 180.0)
        ax[2].set_title('True')
        #
        # Grid learned likelihood data
        #
        logp = net['posterior'].net.log_prob(
            grid, context=theta.expand(len(grid), -1))
        logp = logp.detach().numpy()
        logp = logp.reshape(glong_grid.shape)
        cax3 = ax[3].imshow(
            logp-logp.max(), extent=extent, origin='lower',
            interpolation='none', vmin=-20.0, vmax=0.0, aspect='auto')
        ax[3].set_xlabel('VLSR (km/s)')
        ax[3].set_xlim(-150.0, 150.0)
        ax[3].set_ylim(-180.0, 180.0)
        ax[3].set_title('Learned')
        #
        # Add colorbars
        #
        fig.canvas.draw_idle()
        cbar_ax1 = fig.add_axes([0.075, 0.1, 0.45, 0.025])
        plt.colorbar(
            cax1, cax=cbar_ax1, orientation='horizontal',
            label='Latitude (deg)')
        cbar_ax2 = fig.add_axes([0.5375, 0.1, 0.45, 0.025])
        plt.colorbar(
            cax3, cax=cbar_ax2, orientation='horizontal',
            label=r'log $L + C$ ($b = 0^\circ$)')
        fname = os.path.join(outdir, 'frame_{0:03d}.png'.format(i))
        fig.savefig(fname, dpi=100)
        plt.close(fig)

if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(
        description="Plot likelihood data",
        prog="plot_likelihoods.py",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    PARSER.add_argument(
        "net", type=str,
        help="Neural network pickle filename")
    PARSER.add_argument(
        "--outdir", type=str, default="frames",
        help="Directory where images are saved")
    ARGS = vars(PARSER.parse_args())
    main(ARGS['net'], outdir=ARGS['outdir'])
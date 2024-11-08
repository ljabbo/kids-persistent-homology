import os
from typing import Union, List

import matplotlib.pyplot as plt
import numpy as np

from analysis.map import Map
import analysis.cosmologies as cosmologies
from utils import file_system

class PersistenceDiagram:

	def __init__(self, maps: List[Map], cosmology=None, do_delete_maps=False, lazy_load=False, recalculate=False, plots_dir='plots', products_dir='products'):
		self.lazy_load = lazy_load
		self.recalculate = recalculate

		if cosmology is None:
			self.cosmology = maps[0].cosmology
			self.cosmology_id = maps[0].cosmology_id
		else:
			self.cosmology = cosmology
			self.cosmology_id = None

		self.zbin = maps[0].zbin
		self.los = maps[0].los

		# if len(maps) == 1:
		# 	# Save the line of sight discriminator if we only have one map
		# 	if hasattr(maps[0], 'filename_without_folder'):
		# 		self.los = maps[0].filename_without_folder
		# 		self.product_loc = os.path.join(products_dir, 'persistence_diagrams', self.cosmology, self.los)
		# 		self.plot_loc = os.path.join(plots_dir, 'persistence_diagrams', self.cosmology, self.los)
		# 	else:
		# 		raise ValueError('No los discriminator found')
		# else:		
		# 	self.product_loc = os.path.join(products_dir, 'persistence_diagrams', self.cosmology)
		# 	self.plot_loc = os.path.join(plots_dir, 'persistence_diagrams', self.cosmology)

		self.set_products_loc(products_dir)
		self.set_plots_loc(plots_dir)

		self.cosm_parameters_full = cosmologies.get_cosmological_parameters(self.cosmology_id).to_dict('records')[0]
		self.cosm_parameters = cosmologies.get_cosmological_parameters(self.cosmology_id)[['id', 'Omega_m', 'S_8', 'h', 'w_0']].to_dict('records')[0]

		self.handle_maps(maps, do_delete_maps)

	def set_plots_loc(self, plots_loc):
		self.plot_loc = os.path.join(plots_loc, 'persistence_diagrams', self.zbin, f'Cosmol{self.cosmology_id}', f'LOS{self.los}')

	def set_products_loc(self, products_loc):
		self.product_loc = os.path.join(products_loc, 'persistence_diagrams', self.zbin, f'Cosmol{self.cosmology_id}', f'LOS{self.los}')
		file_system.check_folder_exists(self.product_loc)

	def handle_maps(self, maps, do_delete_maps):
		self.maps_count = len(maps)
		self.maps = maps

		# Recalculate when one of products don't exist
		if not (
				os.path.exists(os.path.join(self.product_loc, 'dimension_pairs_0.npy'))
				and
				os.path.exists(os.path.join(self.product_loc, 'dimension_pairs_1.npy'))
			) or self.recalculate:

			if len(maps) > 0:
				self.dimension_pairs = maps[0].dimension_pairs.copy()
				self.dimension_pairs_count = np.zeros(2)				

				self.dimension_pairs_list = []

				for map in maps[1:]:
					self.dimension_pairs_list.append(map.dimension_pairs)
					for dimension in self.dimension_pairs:
						self.dimension_pairs[dimension] = np.append(self.dimension_pairs[dimension], map.dimension_pairs[dimension], axis=0)
				
				del self.dimension_pairs['all']

				for dim in self.dimension_pairs:
					# np.min collapses the isfinite check to cover the pair of values instead of only one coordinate
					self.dimension_pairs[dim] = self.dimension_pairs[dim][np.min(np.isfinite(self.dimension_pairs[dim]), axis=1)]
					self.dimension_pairs_count[dim] = self.dimension_pairs[dim].shape[0]

					# Save dimension pairs to products
					np.save(os.path.join(self.product_loc, f'dimension_pairs_{dim}.npy'), self.dimension_pairs[dim])

				np.save(os.path.join(self.product_loc, 'dimension_pairs_count.npy'), self.dimension_pairs_count)

			if self.lazy_load:
				del self.dimension_pairs
		elif not self.lazy_load:
			self._load()

		if do_delete_maps:
			del self.maps

	def _load(self, item):
		if item == 'dimension_pairs':
			self.dimension_pairs = {dim: np.load(os.path.join(self.product_loc, f'dimension_pairs_{dim}.npy')) for dim in [0, 1]}
		elif item == 'dimension_pairs_count':
			self.dimension_pairs_count = np.load(os.path.join(self.product_loc, 'dimension_pairs_count.npy'))

	def __getattr__(self, item):
		if item == 'lazy_load':
			return super().__getattribute__('lazy_load')
		# Just return if not lazy loading
		if not self.lazy_load:
			return super().__getattribute__(item)

		if item == 'dimension_pairs':
			self._load('dimension_pairs')
			return self.dimension_pairs

		if item == 'dimension_pairs_count':
			self._load('dimension_pairs_count')
			return self.dimension_pairs_count
		# Every other item can just be returned
		return super().__getattribute__(item)

	def plot(self, close=True, plot_args=None, ax=None):
		if plot_args is None:
			plot_args = {
				's': 3
			}
		new_ax = ax is None
		# Scatter each dimension separately
		if new_ax:
			fig, ax = plt.subplots()
		ax.set_xlabel('Birth threshold $\kappa$')
		ax.set_ylabel('Death threshold $\kappa$')
		for dimension in self.dimension_pairs:
			# Turn into np array for easy slicing
			pairs = self.dimension_pairs[dimension]

			# ax.scatter(pairs[np.isfinite(np.linalg.norm(pairs, axis=1)), 0], pairs[np.isfinite(np.linalg.norm(pairs, axis=1)), 1], label=f'{dimension}', s=3)
			ax.scatter(pairs[:, 0], pairs[:, 1], label=f'Dgm$_{dimension}$', **plot_args)
		
		ax.legend()
		lim = 0.05
		ax.set_ylim(ymin=-lim, ymax=lim)
		ax.set_xlim(xmin=-lim, xmax=lim)

		eq_line = np.linspace(-lim, lim, 2)
		ax.plot(eq_line, eq_line, linestyle='--', color='grey')

		# ax.set_title(self.cosmology)
		file_system.check_folder_exists(os.path.join(self.plot_loc))
		fig.tight_layout()
		fig.savefig(os.path.join(self.plot_loc, 'persistence_diagram.pdf'))

		if not new_ax:
			return

		if close:
			plt.close(fig)
			return
		else:
			return fig, ax

	def add_average_lines(self):
		# Average death and birth
		self.ax.axhline(y=np.average(self.dimension_pairs['all'][:, 1][np.isfinite(self.dimension_pairs['all'][:, 1])]), linestyle='--', color='black')
		self.ax.axvline(x=np.average(self.dimension_pairs['all'][:, 0][np.isfinite(self.dimension_pairs['all'][:, 0])]), linestyle='--', color='black')
		
		# Average of map
		all_maps_avg = np.average([np.average(map.map) for map in self.maps])
		self.ax.axvline(x=all_maps_avg, linestyle='--', color='grey')
		self.ax.axhline(y=all_maps_avg, linestyle='--', color='grey')

	def get_persistent_betti_numbers(self, birth_before: np.ndarray, death_after: np.ndarray, dimension):

		# Count the number of scatter points that have birth < birth_before and death > death_after
		pairs = self.dimension_pairs[dimension]

		number_of_features = pairs.shape[0]
		number_of_test_coords = birth_before.shape[0]

		birth_check = np.less(
			np.broadcast_to(pairs[:, 0], (number_of_test_coords, number_of_features)), 
			birth_before.reshape((-1, 1))
		)
		death_check = np.greater(
			np.broadcast_to(pairs[:, 1], (number_of_test_coords, number_of_features)), 
			death_after.reshape((-1, 1))
		)

		# Broadcast one array from [[a, b, c], [d, e, f]] to [[[a, b, c], [d, e, f]], [[a, b, c], [d, e, f]]]
		# The other from [[a, b, c], [d, e, f]] to [[[a, b, c], [a, b, c]], [[d, e, f], [d, e, f]]]
		# to be able to multiply and find every combination of born before and died after check
		birth_side = np.broadcast_to(birth_check, (number_of_test_coords, number_of_test_coords, number_of_features))
		death_side = np.repeat(death_check, number_of_test_coords, axis=0).reshape(number_of_test_coords, number_of_test_coords, number_of_features)

		return np.sum(birth_side * death_side, axis=2)
	
	def generate_betti_numbers_grids(self, resolution=100, data_ranges_dim=None, save_plots=False):
		
		self.betti_numbers_grids = {}

		if not self.recalculate:
			if os.path.exists(os.path.join(self.product_loc, 'betti_number_grids')):
				self.betti_numbers_grids[0] = load_betti_numbers_grid(os.path.join(self.product_loc, 'betti_number_grids'), 0)
				self.betti_numbers_grids[1] = load_betti_numbers_grid(os.path.join(self.product_loc, 'betti_number_grids'), 1)
				return self.betti_numbers_grids

		for dimension in self.dimension_pairs:
			if dimension == 'all':
				continue

			data_range = [
				np.min(self.dimension_pairs[dimension]), 
				np.max(self.dimension_pairs[dimension])
			]

			if data_ranges_dim is None:
				birth_linspace = np.linspace(*data_range, resolution)
				death_linspace = np.linspace(*data_range, resolution)
			else:
				birth_linspace = np.linspace(*data_ranges_dim[dimension], resolution)
				death_linspace = np.linspace(*data_ranges_dim[dimension], resolution)

			betti_numbers_grid = np.zeros((resolution, resolution))

			betti_numbers_grid = self.get_persistent_betti_numbers(birth_linspace, death_linspace, dimension)
			# Normalize
			betti_numbers_grid = betti_numbers_grid / np.max(betti_numbers_grid)
			
			self.betti_numbers_grids[dimension] = BettiNumbersGrid(betti_numbers_grid, 
				[birth_linspace[0], birth_linspace[-1]], 
				[death_linspace[0], death_linspace[-1]], 
				dimension=dimension
			)
			
			self.betti_numbers_grids[dimension].save(os.path.join(self.product_loc, 'betti_numbers_grid'))

			if save_plots:
				self.betti_numbers_grids[dimension].save_figure(
					os.path.join(self.plot_loc, 'betti_number_grids'), 
					scatter_points=(self.dimension_pairs[dimension][:, 0], self.dimension_pairs[dimension][:, 1])
				)

			if self.lazy_load:
				del self.dimension_pairs
		
		return self.betti_numbers_grids


	def generate_heatmaps(self, resolution=1000, gaussian_kernel_size_in_sigma=3):
		"""
		Generates the heatmaps corresponding to the birth and death times given calculated by get_persistence.
		The heatmap is a convolution of the birth and death times (scatterplot) with a 2D Gaussian.
		:param resolution: The number of pixels in one axis, the resulting heatmap is always a square of size resolution x resolution
		"""
		from scipy.signal import convolve2d
		from scipy.signal.windows import gaussian

		self.heatmaps = {}

		if not self.recalculate and os.path.exists(os.path.join(self.product_loc, 'heatmaps')):
			self.heatmaps[0] = load_heatmap(os.path.join(self.product_loc, 'heatmaps'), 0)
			self.heatmaps[1] = load_heatmap(os.path.join(self.product_loc, 'heatmaps'), 1)
			return self.heatmaps

		# convolve2d takes two arrays as input
		# We need to generate a 2D array with 1s in the spot of each (birth, death) scatter point
		# which will be convolved with a 2D Gaussian

		# The 2D map of the scatter points still has the same min and max in x and y
		for dimension in self.dimension_pairs:
			if dimension == 'all':
				continue

			x = self.dimension_pairs[dimension][:, 0]
			y = self.dimension_pairs[dimension][:, 1]

			# We want each pixel to be a square, so we need to find the largest range of values to cover
			data_range = [
				np.min(self.dimension_pairs[dimension][np.isfinite(self.dimension_pairs[dimension])]), 
				np.max(self.dimension_pairs[dimension][np.isfinite(self.dimension_pairs[dimension])])
			]

			# range = [x_range, y_range], set to equal so we have square pixels
			hist, bin_edges_x, bin_edges_y = np.histogram2d(x, y, bins=resolution, range=[data_range, data_range])

			# Scale parameter of the Gaussian
			pixel_scale = np.abs(data_range[1] - data_range[0]) / resolution
			# Determine the scale parameter (std, sigma) of the Gaussian kernel
			# Set to 1/25th of the range, similar value as Heydenreich+2022
			scale_parameter = 1. / 25. * np.abs(data_range[1] - data_range[0])

			sigma_in_pixel = scale_parameter / pixel_scale
			gaussian_size_in_pixel = sigma_in_pixel * 2 * gaussian_kernel_size_in_sigma  # Two times because symmetric Gaussian with both sides

			gaussian_kernel1d = gaussian(np.round(gaussian_size_in_pixel), std=sigma_in_pixel)
			gaussian_kernel = np.outer(gaussian_kernel1d, gaussian_kernel1d)

			heatmap = convolve2d(hist, gaussian_kernel, mode='same')
		
			self.heatmaps[dimension] = Heatmap(heatmap, data_range, data_range, dimension)

			self.heatmaps[dimension].save(os.path.join(self.product_loc, 'heatmaps'))

			self.heatmaps[dimension].save_figure(os.path.join(self.plot_loc, 'heatmaps'))#, scatter_points=(x, y))
		
		return self.heatmaps


def load_heatmap(path, dimension):
	"""
	Loads a saved Heatmap from path.
	If directory structure is as follows:
	/data/heatmaps/hm1/
				heatmap_0.py
				heatmap_1.py
				birth_range0.py
				birth_range1.py
				death_range0.py
				death_range1.py
	Then the heatmap of dimension 0 can be loaded through
		load_heatmap('/data/heatmaps/hm1', 0)
	or dimension 1
		load_heatmap('/data/heatmaps/hm1', 1)
	"""
	return _load_ranged_map(path, dimension, Heatmap)


def load_betti_numbers_grid(path, dimension):
	return _load_ranged_map(path, dimension, BettiNumbersGrid)


def load_betti_numbers_variance_map(path, dimension):
	return _load_ranged_map(path, dimension, BettiNumbersGridVarianceMap)


def _load_ranged_map(path, dimension, map_type):
	rmap = map_type(None, None, None, dimension)
	rmap.load(path)
	return rmap

	
class BaseRangedMap:

	def __init__(self, map, x_range, y_range, dimension, name):
		self.name = name
		self.map = map
		self.x_range = x_range
		self.y_range = y_range
		self.dimension = dimension
	
	def save(self, path):
		file_system.check_folder_exists(path)
		np.save(os.path.join(path, f'{self.name}_{self.dimension}.npy'), self.map)
		np.save(os.path.join(path, f'x_range_{self.dimension}.npy'), self.x_range)
		np.save(os.path.join(path, f'y_range_{self.dimension}.npy'), self.y_range)

	def load(self, path):
		self.map = np.load(os.path.join(path, f'{self.name}_{self.dimension}.npy'))
		self.x_range = np.load(os.path.join(path, f'x_range_{self.dimension}.npy'))
		self.y_range = np.load(os.path.join(path, f'y_range_{self.dimension}.npy'))

	def get_axis_values(self, axis):
		if axis == 'x':
			return np.linspace(*self.x_range, num=len(self.map[0]))
		elif axis == 'y':
			return np.linspace(*self.y_range, num=len(self.map))
		
	def plot(self, scatter_points=None, title=None, scatters_are_index=False, heatmap_scatter_points=False, cbar_label='$\kappa$'):
		fig, ax = plt.subplots()
		imax = ax.imshow(self._transform_map(), aspect='equal', extent=(*self.x_range, *self.y_range))
		cbar = fig.colorbar(imax)
		cbar.set_label(cbar_label)

		if scatter_points is not None:
			c = 'red' if not heatmap_scatter_points else np.arange(0, len(scatter_points[0]), step=1)
			cmap = 'Greys' if heatmap_scatter_points else None
			if not scatters_are_index:
				ax.scatter(*scatter_points, s=3, alpha=.6, c=c, cmap=cmap)
			else:
				x_values = self.get_axis_values('x')[scatter_points[0]]
				y_values = self.get_axis_values('y')[::-1][scatter_points[1]]
				ax.scatter(x_values, y_values, s=3, alpha=.6, c=c, cmap=cmap)

		if title is not None:
			ax.set_title(title)

		ax.set_xlabel('Birth threshold $\kappa$')
		ax.set_ylabel('Death threshold $\kappa$')

		return fig, ax

	def save_figure(self, path, scatter_points=None, title=None, save_name=None):
		file_system.check_folder_exists(path)
		
		fig, ax = self.plot(scatter_points, title)
		fig.tight_layout()

		if save_name is None:
			fig.savefig(os.path.join(path, f'{self.name}_{self.dimension}.pdf'))
		else:
			fig.savefig(os.path.join(path, f'{self.name}_{self.dimension}_{save_name}.pdf'))
		plt.close(fig)

	def _transform_map(self):
		return self.map
	

class Heatmap(BaseRangedMap):

	def __init__(self, heatmap, birth_range, death_range, dimension):
		super().__init__(heatmap, birth_range, death_range, dimension, name='heatmap')

	def _transform_map(self):
		return self.map.T[::-1,:]


class BettiNumbersGrid(BaseRangedMap):

	def __init__(self, betti_numbers_grid, birth_range, death_range, dimension):
		super().__init__(betti_numbers_grid, birth_range, death_range, dimension, name='betti_numbers_grid')

	def _transform_map(self):
		return self.map[::-1, :]
	
	def plot(self, scatter_points=None, title=None, scatters_are_index=False, heatmap_scatter_points=False):
		return super().plot(scatter_points, title, scatters_are_index, heatmap_scatter_points, cbar_label=f'Normalized $\\beta_{self.dimension}(t_b, t_d)$')
	

class BettiNumbersGridVarianceMap(BaseRangedMap):

	def __init__(self, betti_numbers_grids: List[BettiNumbersGrid], birth_range=None, death_range=None, dimension=None):
		if birth_range is None:
			birth_range = betti_numbers_grids[0].x_range
		if death_range is None:
			death_range = betti_numbers_grids[0].y_range
		if dimension is None:
			dimension = betti_numbers_grids[0].dimension
		super().__init__(None, birth_range, death_range, dimension, name='betti_numbers_grid_variance_map')

		grids = []
		for bng in betti_numbers_grids:
			grids.append(bng.map)
		
		self.map = np.std(grids, axis=0)

	def _transform_map(self):
		return self.map[::-1, :]
	
	def plot(self, scatter_points=None, title=None, scatters_are_index=False, heatmap_scatter_points=False):
		return super().plot(scatter_points, title, scatters_are_index, heatmap_scatter_points, cbar_label='$\sigma$')


class PixelDistinguishingPowerMap(BaseRangedMap):

	def __init__(self, cosmoslics_bngs: List[BettiNumbersGrid], slics_bng: BettiNumbersGrid, slics_variance: BettiNumbersGridVarianceMap, dimension):
		# Allow for an empty map to be created in which the data is loaded later
		if cosmoslics_bngs is None and slics_bng is None and slics_variance is None:
			super().__init__(None, None, None, dimension, 'pixel_distinguishing_power')
		# If arrays are passed, check that the ranges are the same
		if not np.all([np.allclose(cbng.y_range, slics_bng.y_range) for cbng in cosmoslics_bngs]):
			raise ValueError('Death ranges are different for cosmoSLICS and SLICS BettiNumbersGrids')
		if not np.all([np.allclose(cbng.x_range, slics_bng.x_range) for cbng in cosmoslics_bngs]):
			raise ValueError('Birth ranges are different for cosmoSLICS and SLICS BettiNumbersGrids')
		if not np.all([np.allclose(slics_bng.x_range, slics_variance.x_range), np.allclose(slics_bng.y_range, slics_variance.y_range)]):
			raise ValueError('Ranges of SLICS BettiNumbersGrid and BettiNumbersVarianceGrid are different')
		super().__init__(None, slics_bng.x_range, slics_bng.y_range, dimension, 'pixel_distinguishing_power')

		self.map = np.mean(np.abs((np.array([cbng.map for cbng in cosmoslics_bngs]) - slics_bng.map) / slics_variance.map), axis=0)

	def _transform_map(self):
		return self.map[::-1, :]
	
	def plot(self, scatter_points=None, title=None, scatters_are_index=False, heatmap_scatter_points=False):
		return super().plot(scatter_points, title, scatters_are_index, heatmap_scatter_points, cbar_label='$\sigma$')
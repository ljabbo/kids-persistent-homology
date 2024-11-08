import glob
import json
import os
import numpy as np
import matplotlib.pyplot as plt

from analysis.cosmology_data import CosmologyData
from analysis.map import Map
from analysis.persistence_diagram import BettiNumbersGrid, PersistenceDiagram
from analysis.persistence_diagram import BettiNumbersGridVarianceMap, PixelDistinguishingPowerMap
from utils.is_notebook import is_notebook

if is_notebook():
	from tqdm.notebook import tqdm
else:
	from tqdm import tqdm


class Pipeline:

	def __init__(
			self,
			maps_dir='maps',
			plots_dir='plots', 
			products_dir='products', 
			force_recalculate=False,
			filter_zbin=None,
			filter_region=None,
			filter_cosmology=None,
			filter_los=None,
			do_remember_maps=True,
			save_plots=False,
			bng_resolution=100,
			three_sigma_mask=False,
			lazy_load=False
		):
		self.maps_dir = maps_dir
		self.plots_dir = plots_dir
		self.products_dir = products_dir
		self.recalculate = force_recalculate

		self.filter_zbin = filter_zbin if filter_zbin is not None else '*'
		self.filter_region = filter_region if filter_region is not None else '*'
		self.filter_cosmology = f'Cosmol{filter_cosmology}' if filter_cosmology is not None else '*'
		self.filter_los = filter_los if filter_los is not None else '*'

		self.do_remember_maps = do_remember_maps
		self.save_plots = save_plots
		self.bng_resolution = bng_resolution
		self.three_sigma_mask = three_sigma_mask
		self.lazy_load = lazy_load

		# List of cosmology names
		self.cosmologies = [f'Cosmol{i}' for i in range(25)] + ['Cosmolfid', 'SLICS']

		# List of LOS numbers for cosmoSLICS and SLICS
		# cosmoSLICS: 1 - 50 inclusive
		self.cosmoslics_los = list(range(1, 51))
		# SLICS: 74 - 292 inclusive, excluding 198 & 199
		self.slics_los = list(range(74, 293))
		self.slics_los.remove(198)
		self.slics_los.remove(199)


	def run_pipeline(self):
		self.find_max_min_values_maps()
		self.read_maps()
		self.calculate_variance()

	def _get_glob_str_dir(self, filter_cosmology=None):
		# Always overwrite filter_cosmology option if Pipeline.filter_cosmology is set

		if self.filter_cosmology != '*':
			filter_cosmology = self.filter_cosmology
		
		# SLICS dirs end with the Zbin, which ends with a dot followed by a number
		if filter_cosmology != 'SLICS':
			filter_cosmology = f'_{filter_cosmology}'
		elif self.filter_zbin != '*':
			filter_cosmology = ''
		else:
			filter_cosmology =  '.[0-9]'

		return f'{self.maps_dir}/MRres140.64arcs_100Sqdeg_SN*_Mosaic_KiDS1000GpAM_zKiDS1000_{self.filter_zbin}{filter_cosmology}'

	def _get_glob_str_file(self, dir, filter_los='*'):
		# file_f = '*SN0*.npy' if self.filter_region is None else f'*SN0*R{self.filter_region}.S*.npy'
		# dir_f = f'{dir}' if self.filter_cosmology is None else f'{dir}'
		# return f'{dir}/*SN0*.npy' if self.filter_region is None else f'{dir}/*SN0*R{self.filter_region}.S*.npy'

		# Overwrite filter_los if Pipeline.filter_los is set
		if self.filter_los != '*':
			filter_los = self.filter_los
	
		return dir + f'/SN0*LOS{filter_los}R{self.filter_region}.S*.npy'

	def find_max_min_values_maps(self, save_all_values=False, save_maps=False):		
		print('Determining max and min values in maps...')

		self.data_range = {
			dim : [-.05, 0.05] for dim in [0, 1]
		}

		return self.data_range

		if os.path.exists(os.path.join(self.maps_dir, 'extreme_values.json')): # and not self.recalculate:
			print('Found file with saved values, reading...')
			with open(os.path.join(self.maps_dir, 'extreme_values.json')) as file:
				data_range_read = json.loads(file.readline())

				# JSON format does not allow for int as key, so we change from str keys to int keys
				self.data_range = {dim: data_range_read[str(dim)] for dim in [0, 1]}
				return self.data_range
		
		vals = {
			'min': np.inf,
			'max': -np.inf
		}

		self.all_values = []
		self.all_values_cosm = {}
		self.all_maps = []
		
		for dir in tqdm(glob.glob(self._get_glob_str_dir())):
			if os.path.isdir(dir):
				for i, map_path in enumerate(glob.glob(self._get_glob_str_file(dir))):
					if 'LOS0' in map_path:# or 'LOS10' in map_path or 'LOS46' in map_path:
						continue

					map = Map(map_path, three_sigma_mask=self.three_sigma_mask, lazy_load=self.lazy_load)

					curr_min = np.min(map.map[np.isfinite(map.map)])
					curr_max = np.max(map.map[np.isfinite(map.map)])

					# Diagnostic check
					if curr_min < -.1:
						print('min check', map_path)
					if curr_max > .1:
						print('max check', map_path)
					
					if curr_min < vals['min']:
						vals['min'] = curr_min
					if curr_max > vals['max']:
						vals['max'] = curr_max

					if save_all_values:
						self.all_values += map.map[np.isfinite(map.map)].flatten().tolist()
						# self.all_values_cosm[map.cosmology_id] = map.map[np.isfinite(map.map)].flatten().tolist()

					if save_maps:
						self.all_maps.append(map)
		
		print('min=', vals['min'])
		print('max=', vals['max'])

		self.data_range = {
			dim : [-.05, 0.05] for dim in [0, 1]
		}

		with open(os.path.join(self.maps_dir, 'extreme_values.json'), 'w') as file:
			file.write(json.dumps(self.data_range))

		return self.data_range

	def all_values_histogram(self, ax=None):		
		if ax is None:
			fig, ax = plt.subplots()
		ax.hist(self.all_values, bins=500)
		# ax.semilogy()

		# fig, ax = plt.subplots()
		# hists = []
		# bine = np.arange(-.05, .05, .001)
		# binc = (bine + .001)[:-1]
		# for csm, vals in self.all_values_cosm.items():
		# 	h, _ = np.histogram(vals, bins=bine)
		# 	hists.append(h)
		# 	ax.scatter(binc, h, color='grey', s=2, alpha=.3)
		
		# ax.scatter(binc, np.average(hists, axis=0), color='red', s=2)
		
		# ax.legend()

	def read_maps(self):

		print(self.data_range)

		# SLICS determines the sample variance, will be a list of persistence diagrams for each line of sight
		self.slics_pds = []
		# cosmoSLICS is different cosmologies, will be a list of persistence diagrams for each cosmology
		self.cosmoslics_pds = []
		# cosmoslics_uniq_pds = []

		# self.slics_maps = []
		# cosmoslics_maps = []
  
		self.cosmoslics_datas = []
		self.slics_data = None

		do_delete_maps = not self.do_remember_maps

		print('Analyzing maps...')
		# For each cosmology
		cosm_tqdm = tqdm(self.cosmologies)
		for cosmology in cosm_tqdm:
			cosm_tqdm.set_description(f'{cosmology}')
			curr_cosm_zbins = {}
			# For each redshift bin
			zbin_tqdm = tqdm(glob.glob(self._get_glob_str_dir(filter_cosmology=cosmology)), leave=False)
			for dir in zbin_tqdm:
				if os.path.isdir(dir):
					zbin_tqdm.write(f'Processing maps in {dir}')

					# Track all persistence diagrams
					curr_zbin_pds = []

					# For each LOS
					los_list = self.slics_los if cosmology == 'SLICS' else self.cosmoslics_los
					for los in los_list:
						curr_los_maps = []
						glob_str = self._get_glob_str_file(dir, filter_los=los)
						# For each map
						for i, map_path in enumerate(glob.glob(glob_str)):
							los_map = Map(map_path, three_sigma_mask=self.three_sigma_mask, lazy_load=self.lazy_load)
							zbin = los_map.zbin
							curr_los_maps.append(los_map)
							
						# One PersistenceDiagram per LOS, combining regions
						perdi = PersistenceDiagram(
							curr_los_maps, do_delete_maps=do_delete_maps, lazy_load=self.lazy_load, recalculate=self.recalculate,
							plots_dir=self.plots_dir, products_dir=self.products_dir
						)
						perdi.generate_betti_numbers_grids(resolution=self.bng_resolution, data_ranges_dim=self.data_range, save_plots=False)
						curr_zbin_pds.append(perdi)
			
				curr_cosm_zbins[zbin] = curr_zbin_pds
			
			if cosmology != 'SLICS':
				self.cosmoslics_datas.append(CosmologyData(cosmology, curr_cosm_zbins))
			else:
				# Put it in a list to make our live easier when compressing
				# By making both cosmoslics_datas and slics_data a list, we can handle them the same in Compressor._build_training_set
				self.slics_data = [CosmologyData(cosmology, curr_cosm_zbins, n_cosmoslics_los=len(curr_zbin_pds))]

		self.zbins = list(self.slics_data[0].zbins_pds.keys())

		return self.slics_data, self.cosmoslics_datas

	def calculate_variance(self):
		print('Calculating SLICS/cosmoSLICS variance maps...')

		self.dist_powers = {}
		for zbin in self.zbins:
			self.dist_powers[zbin] = []
			for dim in [0,1]:
				self.dist_powers[zbin].append(PixelDistinguishingPowerMap(
					[cdata.zbins_bngs_avg[zbin][dim] for cdata in self.cosmoslics_datas],
					self.slics_data[0].zbins_bngs_avg[zbin][dim],
					self.slics_data[0].zbins_bngs_std[zbin][dim],
					dimension=dim
				))

				self.dist_powers[zbin][dim].save_figure(os.path.join(self.plots_dir, 'pixel_distinguishing_power'), save_name=zbin)
		
		return self.dist_powers

		# slics_bngs = {
		# 	dim: [spd.betti_numbers_grids[dim] for spd in self.slics_pds] for dim in [0, 1]
		# }
		# cosmoslics_bngs = {
		# 	dim: [cpd.betti_numbers_grids[dim] for cpd in self.cosmoslics_pds] for dim in [0, 1]
		# }

		# # slics_pd = PersistenceDiagram(
		# # 	self.slics_maps, lazy_load=self.lazy_load, recalculate=self.recalculate,
		# # 	plots_dir=self.plots_dir, products_dir=self.products_dir
		# # )
		# # slics_pd.generate_betti_numbers_grids(data_ranges_dim=self.data_range, resolution=self.bng_resolution)
		# avg_slics_bng = {
		# 	dim: BettiNumbersGrid(np.mean([bng.map for bng in slics_bngs[dim]], axis=0), slics_bngs[dim][0].x_range, slics_bngs[dim][0].y_range, dim) for dim in [0, 1]
		# }

		# # dist_powers must have shape (zbins, 2, 100, 100)

		# self.dist_powers = []

		# for i, bngs in enumerate([slics_bngs, cosmoslics_bngs]):
		# 	t = 'SLICS' if i == 0 else 'cosmoSLICS'
		# 	for dim in [0, 1]:
		# 		# Calculate Variance map
		# 		var_map = BettiNumbersGridVarianceMap(bngs[dim], birth_range=self.data_range[dim], death_range=self.data_range[dim], dimension=dim)
		# 		if t == 'SLICS':
		# 			# SLICS variance needs to be divided by sqrt(n_cosmoSLICS_realizations)
		# 			var_map.map = var_map.map / np.sqrt(len(self.cosmoslics_los))

		# 		var_map.save(os.path.join(self.products_dir, 'bng_variance', t))

		# 		if self.save_plots:
		# 			var_map.save_figure(os.path.join(self.plots_dir, 'bng_variance', t), title=f'{t} variance, dim={dim}')

		# 		# Calculate pixel distinguishing power map if SLICS
		# 		if t == 'SLICS':
		# 			dist_power = PixelDistinguishingPowerMap([cpd.betti_numbers_grids[dim] for cpd in self.cosmoslics_pds], avg_slics_bng[dim], var_map, dimension=dim)
		# 			dist_power.save(os.path.join(self.products_dir, 'pixel_distinguishing_power'))
				
		# 			if self.save_plots:
		# 				dist_power.save_figure(os.path.join(self.plots_dir, 'pixel_distinguishing_power'))

		# 			self.dist_powers.append(dist_power)

		# # del slics_pd
		# # del self.slics_maps

		# return self.dist_powers
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 10:37:08 2020

@author: marcoaqil
"""
import os
import numpy as np
import matplotlib.pyplot as pl
import cortex
import nibabel as nb
from collections import defaultdict as dd

import time
from scipy.stats import sem, ks_2samp, ttest_1samp, wilcoxon

opj = os.path.join

from statsmodels.stats import weightstats
from sklearn.linear_model import LinearRegression
from nibabel.freesurfer.io import read_morph_data, write_morph_data
from utils.utils import roi_mask

class visualize_results(object):
    def __init__(self):
        self.main_dict = dd(lambda:dd(lambda:dd(dict)))
        
    def transfer_parse_labels(self, fs_dir):
        self.idx_rois = dd(dict)
        for subj in self.subjects:
            if self.transfer_rois:
                src_subject='fsaverage'
            else:
                src_subject=subj
                    
            self.fs_dir = fs_dir
        
            wang_rois = ["V1v", "V1d", "V2v", "V2d", "V3v", "V3d", "hV4", "VO1", "VO2", "PHC1", "PHC2",
                "TO2", "TO1", "LO2", "LO1", "V3B", "V3A", "IPS0", "IPS1", "IPS2", "IPS3", "IPS4", 
                "IPS5", "SPL1", "FEF"]
            for roi in wang_rois:
                try:
                    self.idx_rois[subj][roi], _ = cortex.freesurfer.get_label(subject=subj,
                                                          label='wang2015atlas.'+roi,
                                                          fs_dir=self.fs_dir,
                                                          src_subject=src_subject)
                except Exception as e:
                    print(e)
        
            self.idx_rois[subj]['visual_system'] = np.concatenate(tuple([self.idx_rois[subj][roi] for roi in self.idx_rois[subj]]), axis=0)
            self.idx_rois[subj]['V1']=np.concatenate((self.idx_rois[subj]['V1v'],self.idx_rois[subj]['V1d']))
            self.idx_rois[subj]['V2']=np.concatenate((self.idx_rois[subj]['V2v'],self.idx_rois[subj]['V2d']))
            self.idx_rois[subj]['V3']=np.concatenate((self.idx_rois[subj]['V3v'],self.idx_rois[subj]['V3d']))
        
            #parse custom ROIs if they have been created
            for roi in ['custom.V1','custom.V2','custom.V3']:
                try:
                    self.idx_rois[subj][roi], _ = cortex.freesurfer.get_label(subject=subj,
                                                          label=roi,
                                                          fs_dir=self.fs_dir,
                                                          src_subject=subj)
                except Exception as e:
                    print(e)
                    pass
                
            #For ROI-based fitting
            if self.output_custom_V1V2V3:
                V1V2V3 = np.concatenate((self.idx_rois[subj]['custom.V1'],self.idx_rois[subj]['custom.V2'],self.idx_rois[subj]['custom.V3']))
                np.save('/Users/marcoaqil/PRFMapping/PRFMapping-Deriv-hires/prfpy/'+subj+'_roi-V1V2V3.npy', V1V2V3)
        

    def set_alpha(self):
        self.tc_min = dict()
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                for analysis, analysis_res in space_res.items():       
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
                        
                        if subj not in cortex.db.subjects:
                            cortex.freesurfer.import_subj(subj, freesurfer_subject_dir=self.fs_dir, 
                                  whitematter_surf='smoothwm')
                        
                        p_r = subj_res['Processed Results']
                        models = p_r['RSq'].keys()
                        
                        tc_stats = subj_res['Timecourse Stats']
                       
                        #######Raw bold timecourse vein threshold
                        if subj == 'sub-006':
                            self.tc_min[subj] = 45000
                        elif subj == 'sub-007':
                            self.tc_min[subj] = 35000
                        elif subj == 'sub-001':
                            self.tc_min[subj] = 35000
                            
                        ######limits for eccentricity
                        self.ecc_min=0.125
                        self.ecc_max=5.0
              
                        #housekeeping
                        rsq = np.vstack(tuple([elem for _,elem in p_r['RSq'].items()])).T
                        ecc = np.vstack(tuple([elem for _,elem in p_r['Eccentricity'].items()])).T
            
                        #alpha dictionary
                        p_r['Alpha'] = {}          
                        p_r['Alpha']['all'] = rsq.max(-1) * (tc_stats['Mean']>self.tc_min[subj]) * (ecc.min(-1)<self.ecc_max) * (ecc.max(-1)>self.ecc_min) * (rsq.min(-1)>0)
                        
                        for model in models:
                            p_r['Alpha'][model] = p_r['RSq'][model] * (p_r['Eccentricity'][model]>self.ecc_min) * (p_r['Eccentricity'][model]<self.ecc_max)\
                                * (tc_stats['Mean']>self.tc_min[subj])
                       


    def pycortex_plots(self, rois, rsq_thresh, analysis_names = 'all'):        
          
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                plotted_rois = dd(lambda:False)
                plotted_stats = dd(lambda:False)
                if analysis_names == 'all':
                    analyses = space_res.items()
                else:
                    analyses = [item for item in space_res.items() if item[0] in analysis_names] 
                for analysis, analysis_res in analyses:    
                    for subj, subj_res in analysis_res.items():
                        
                        if subj not in cortex.db.subjects:
                            cortex.freesurfer.import_subj(subj, freesurfer_subject_dir=self.fs_dir, 
                                  whitematter_surf='smoothwm')
                        
                        p_r = subj_res['Processed Results']
                        models = p_r['RSq'].keys()
                        
                        tc_stats = subj_res['Timecourse Stats']
                        mask = subj_res['Results']['mask']
                        
                        
                        #housekeeping
                        rsq = np.vstack(tuple([elem for _,elem in p_r['RSq'].items()])).T
                        polar = np.vstack(tuple([elem for _,elem in p_r['Polar Angle'].items()])).T
                        ecc = np.vstack(tuple([elem for _,elem in p_r['Eccentricity'].items()])).T
                  
                        if rois != 'all':
                            for key in p_r['Alpha']:
                                p_r['Alpha'][key] = roi_mask(self.idx_rois[subj][rois], p_r['Alpha'][key])
                                         
                        ##START PYCORTEX VISUALIZATIONS
                        #output freesurefer-format polar angle maps to draw custom ROIs in freeview    
                        if self.output_freesurfer_maps:
                                          
                            lh_c = read_morph_data(opj(self.fs_dir, subj+'/surf/lh.curv'))
            
                            polar_freeview = np.mean(polar, axis=-1)
                            ecc_freeview = np.mean(ecc, axis=-1)
                                      
                            alpha_freeview = rsq.max(-1) * (tc_stats['Mean']>self.tc_min[subj]) * (rsq.min(-1)>0)
            
                            polar_freeview[alpha_freeview<rsq_thresh] = -10
                            ecc_freeview[alpha_freeview<rsq_thresh] = -10
            
                            write_morph_data(opj(self.fs_dir, subj+'/surf/lh.polar')
                                                                   ,polar_freeview[:lh_c.shape[0]])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/rh.polar')
                                                                   ,polar_freeview[lh_c.shape[0]:])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/lh.ecc')
                                                                   ,ecc_freeview[:lh_c.shape[0]])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/rh.ecc')
                                                                   ,ecc_freeview[lh_c.shape[0]:])
                            
                            
                            polar_freeview_masked = np.copy(polar_freeview)
                            ecc_freeview_masked = np.copy(ecc_freeview)
                            alpha_freeview_masked = rsq.max(-1) * (tc_stats['Mean']>self.tc_min[subj]) * (rsq.min(-1)>0)* (ecc_freeview<self.ecc_max) * (ecc_freeview>self.ecc_min)
            
                            polar_freeview_masked[alpha_freeview_masked<rsq_thresh] = -10
                            ecc_freeview_masked[alpha_freeview_masked<rsq_thresh] = -10
            
                            write_morph_data(opj(self.fs_dir, subj+'/surf/lh.polar_masked')
                                                                   ,polar_freeview_masked[:lh_c.shape[0]])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/rh.polar_masked')
                                                                   ,polar_freeview_masked[lh_c.shape[0]:])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/lh.ecc_masked')
                                                                   ,ecc_freeview_masked[:lh_c.shape[0]])
                            write_morph_data(opj(self.fs_dir, subj+'/surf/rh.ecc_masked')
                                                                   ,ecc_freeview_masked[lh_c.shape[0]:])
                            
                            
                        #data quality/stats cortex visualization 
                        if space == 'fsnative' and self.plot_stats_cortex and not plotted_stats[subj] :
                            mean_ts_vert = cortex.Vertex2D(tc_stats['Mean'], mask*(tc_stats['Mean']>self.tc_min[subj]), subject=subj, cmap='Jet_2D_alpha')
                            var_ts_vert = cortex.Vertex2D(tc_stats['Variance'], mask*(tc_stats['Mean']>self.tc_min[subj]), subject=subj, cmap='Jet_2D_alpha')
                            tsnr_vert = cortex.Vertex2D(tc_stats['TSNR'], mask*(tc_stats['Mean']>self.tc_min[subj]), subject=subj, cmap='Jet_2D_alpha')
            
                            data_stats ={'mean':mean_ts_vert.raw, 'var':var_ts_vert.raw, 'tsnr':tsnr_vert.raw}
            
                            self.js_handle_stats = cortex.webgl.show(data_stats, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
            
                            plotted_stats[subj] = True
                        
                        if self.plot_rois_cortex and not plotted_rois[subj]:
                            
                            ds_rois = {}
                            data = np.zeros_like(mask).astype('int')
            
                            for i, roi in enumerate(self.idx_rois[subj]):
            
                                roi_data = np.zeros_like(mask)
                                roi_data[self.idx_rois[subj][roi]] = 1
                                if 'custom' not in roi and 'visual' not in roi:
                                    data[self.idx_rois[subj][roi]] = i+1

                                ds_rois[roi] = cortex.Vertex2D(roi_data, roi_data.astype('bool'), subj, cmap='RdBu_r_alpha').raw
            
                                #need a correctly flattened brain to do this
                                #cortex.add_roi(ds_rois[roi], name=roi, open_inkscape=False, add_path=True)
            
                            ds_rois['Wang2015Atlas'] = cortex.Vertex2D(data, data.astype('bool'), subj, cmap='Retinotopy_HSV_2x_alpha').raw
                            self.js_handle_rois = cortex.webgl.show(ds_rois, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
            
                            plotted_rois[subj] = True
                                                    

                            
            
                        if self.plot_rsq_cortex:              
                            ds_rsq = {}
                            if 'CSS' in models and 'Gauss' in models:
                                ds_rsq['CSS - Gauss'] = cortex.Vertex2D(p_r['RSq']['CSS']-p_r['RSq']['Gauss'], p_r['Alpha']['all'], subject=subj,
                                                                          vmin=-0.05, vmax=0.05, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw                
                            if 'DoG' in models and 'Gauss' in models:
                                ds_rsq['DoG - Gauss'] = cortex.Vertex2D(p_r['RSq']['DoG']-p_r['RSq']['Gauss'], p_r['Alpha']['all'], subject=subj,
                                                                      vmin=-0.05, vmax=0.05, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            if 'Norm' in models and 'Gauss' in models:
                                ds_rsq['Norm - Gauss'] = cortex.Vertex2D(p_r['RSq']['Norm']-p_r['RSq']['Gauss'], p_r['Alpha']['all'], subject=subj,
                                                                      vmin=-0.05, vmax=0.05, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            if 'Norm' in models and 'DoG' in models:
                                ds_rsq['Norm - DoG'] = cortex.Vertex2D(p_r['RSq']['Norm']-p_r['RSq']['DoG'], p_r['Alpha']['all'], subject=subj,
                                                                      vmin=-0.05, vmax=0.05, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            if 'Norm' in models and 'CSS' in models:
                                ds_rsq['Norm - CSS'] = cortex.Vertex2D(p_r['RSq']['Norm']-p_r['RSq']['CSS'], p_r['Alpha']['all'], subject=subj, 
                                                                      vmin=-0.05, vmax=0.05, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                                
                            if 'Processed Results' in self.main_dict['T1w'][analysis][subj] and self.compare_volume_surface:
                                ds_rsq_comp={}
                                volume_rsq = self.main_dict['T1w'][analysis][subj]['Processed Results']['RSq']['Norm']
                                ref_img = nb.load(self.main_dict['T1w'][analysis][subj]['Results']['ref_img_path'])
                                
                                #rsq_img = nb.Nifti1Image(volume_rsq, ref_img.affine, ref_img.header)

                                xfm_trans = cortex.xfm.Transform(np.identity(4), ref_img)
                                xfm_trans.save(subj, 'func_space_transform')
                                
                                ds_rsq_comp['Norm CV rsq (volume fit)'] = cortex.Volume2D(volume_rsq.T, volume_rsq.T, subj, 'func_space_transform',
                                                                          vmin=rsq_thresh, vmax=0.6, vmin2=0.05, vmax2=rsq_thresh, cmap='Jet_2D_alpha')
                                ds_rsq_comp['Norm CV rsq (surface fit)'] = cortex.Vertex2D(p_r['RSq']['Norm'], p_r['RSq']['Norm'], subject=subj,
                                                                          vmin=rsq_thresh, vmax=0.6, vmin2=0.05, vmax2=rsq_thresh, cmap='Jet_2D_alpha').raw
                                self.js_handle_rsq_comp = cortex.webgl.show(ds_rsq_comp, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)

                            self.js_handle_rsq = cortex.webgl.show(ds_rsq, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True) 
                            
                        if self.plot_ecc_cortex:
                            ds_ecc = {}
                            for model in models:
                                ds_ecc[model] = cortex.Vertex2D(p_r['Eccentricity'][model], p_r['Alpha'][model], subject=subj, 
                                                                vmin=self.ecc_min, vmax=self.ecc_max, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_r_2D_alpha').raw
            
                            self.js_handle_ecc = cortex.webgl.show(ds_ecc, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
            
                        if self.plot_polar_cortex:
                            ds_polar = {}
                            for model in models:
                                ds_polar[model] = cortex.Vertex2D(p_r['Polar Angle'][model], p_r['Alpha'][model], subject=subj, 
                                                                  vmin2=rsq_thresh, vmax2=0.6, cmap='Retinotopy_HSV_2x_alpha').raw
                            
                            if 'Processed Results' in self.main_dict['T1w'][analysis][subj] and self.compare_volume_surface:
                                ds_polar_comp={}
                                volume_rsq = self.main_dict['T1w'][analysis][subj]['Processed Results']['RSq']['Norm']
                                volume_polar = self.main_dict['T1w'][analysis][subj]['Processed Results']['Polar Angle']['Norm']
                                ref_img = nb.load(self.main_dict['T1w'][analysis][subj]['Results']['ref_img_path'])                                

                                xfm_trans = cortex.xfm.Transform(np.identity(4), ref_img)
                                xfm_trans.save(subj, 'func_space_transform')
                                
                                ds_polar_comp['Norm CV polar (volume fit)'] = cortex.Volume2D(volume_polar.T, volume_rsq.T, subj, 'func_space_transform',
                                                                          vmin2=0.05, vmax2=rsq_thresh, cmap='Retinotopy_HSV_2x_alpha')
                                ds_polar_comp['Norm CV polar (surface fit)'] = cortex.Vertex2D(p_r['Polar Angle']['Norm'], p_r['RSq']['Norm'], subject=subj,
                                                                          vmin2=0.05, vmax2=rsq_thresh, cmap='Retinotopy_HSV_2x_alpha').raw
                                self.js_handle_polar_comp = cortex.webgl.show(ds_polar_comp, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)

                            
                            self.js_handle_polar = cortex.webgl.show(ds_polar, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
            
                        if self.plot_size_cortex:
                            ds_size = {}
                            for model in models:
                                ds_size[model] = cortex.Vertex2D(p_r['Size (fwhmax)'][model], p_r['Alpha'][model], subject=subj, 
                                                                 vmin=0, vmax=6, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                  
                            self.js_handle_size = cortex.webgl.show(ds_size, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
            
            
                        if self.plot_amp_cortex:
                            ds_amp = {}
                            for model in models:
                                ds_amp[model] = cortex.Vertex2D(p_r['Amplitude'][model], p_r['Alpha'][model], subject=subj, 
                                                                vmin=-1, vmax=1, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
            
                            self.js_handle_amp = cortex.webgl.show(ds_amp, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
                            
                        if self.plot_css_exp_cortex and 'CSS' in models:
                            ds_css_exp = {}
                            ds_css_exp['CSS Exponent'] = cortex.Vertex2D(p_r['CSS Exponent']['CSS'], p_r['Alpha']['CSS'], subject=subj, 
                                                                         vmin=0, vmax=0.75, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
            
                            self.js_handle_css_exp = cortex.webgl.show(ds_css_exp, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)
                            
                        if self.plot_surround_size_cortex:
                            ds_surround_size = {}
                            if 'DoG' in models:
                                ds_surround_size['DoG'] = cortex.Vertex2D(p_r['Surround Size (fwatmin)']['DoG'], p_r['Alpha']['DoG'], subject=subj, 
                                                                         vmin=0, vmax=50, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            if 'Norm' in models:
                                ds_surround_size['Norm'] = cortex.Vertex2D(p_r['Surround Size (fwatmin)']['Norm'], p_r['Alpha']['Norm'], subject=subj, 
                                                                         vmin=0, vmax=50, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw                    
            
                            self.js_handle_surround_size = cortex.webgl.show(ds_surround_size, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)    
                            
                        if self.plot_norm_baselines_cortex and 'Norm' in models:
                            ds_norm_baselines = {}
                            ds_norm_baselines['Norm Param. B'] = cortex.Vertex2D(p_r['Norm Param. B']['Norm'], p_r['Alpha']['Norm'], subject=subj, 
                                                                         vmin=0, vmax=50, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw                    
                            ds_norm_baselines['Norm Param. D'] = cortex.Vertex2D(p_r['Norm Param. D']['Norm'], p_r['Alpha']['Norm'], subject=subj, 
                                                                         vmin=0, vmax=50, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            ds_norm_baselines['Ratio (B/D)'] = cortex.Vertex2D(p_r['Ratio (B/D)']['Norm'], p_r['Alpha']['Norm'], subject=subj, 
                                                                         vmin=0, vmax=50, vmin2=rsq_thresh, vmax2=0.6, cmap='Jet_2D_alpha').raw
                            
                            self.js_handle_norm_baselines = cortex.webgl.show(ds_norm_baselines, with_curvature=False, with_labels=True, with_rois=True, with_borders=True, with_colorbar=True)    
        print('-----')                              
    
        
    def save_pycortex_views(self, js_handle, base_str):
        views = dict(dorsal=dict(radius=191, altitude=73, azimuth=178, pivot=0),
                     medial=dict(radius=10, altitude=101, azimuth=359, pivot=167),
                     lateral=dict(radius=277, altitude=90, azimuth=177, pivot=123),
                     ventral=dict(radius=221, altitude=131, azimuth=175, pivot=0)
                    )
        
        surfaces = dict(inflated=dict(unfold=1))#,
                       # fiducial=dict(unfold=0.0))
        
        # select path for the generated images on disk
        image_path = '/Users/marcoaqil/PRFMapping/Figures/'
        
        # pattern of the saved images names
        file_pattern = "{base}_{view}_{surface}.png"
        
        # utility functions to set the different views
        prefix = dict(altitude='camera.', azimuth='camera.',
                      pivot='surface.{subject}.', radius='camera.', target='camera.',
                      unfold='surface.{subject}.')
        _tolists = lambda p: {prefix[k]+k:[v] for k,v in p.items()}
        _combine = lambda a,b: ( lambda c: [c, c.update(b)][0] )(dict(a))
        
        
        # Save images by iterating over the different views and surfaces
        for view,vparams in views.items():
            for surf,sparams in surfaces.items():
                # Combine basic, view, and surface parameters
                params = _combine(vparams, sparams)
                # Set the view
                print(params)
                time.sleep(5)
                js_handle._set_view(**_tolists(params))
                time.sleep(5)
                # Save image
                filename = file_pattern.format(base=base_str, view=view, surface=surf)
                output_path = os.path.join(image_path, filename)
                js_handle.getImage(output_path, size =(3000, 2000))
        
                # the block below trims the edges of the image:
                # wait for image to be written
                while not os.path.exists(output_path):
                    pass
                time.sleep(0.5)
                try:
                    import subprocess
                    subprocess.call(["convert", "-trim", output_path, output_path])
                except:
                    pass
        
    def ecc_size_roi_plots(self, rois, rsq_thresh, save_figures, analysis_names = 'all'):
        
        pl.rcParams.update({'font.size': 16})
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                if analysis_names == 'all':
                    analyses = space_res.items()
                else:
                    analyses = [item for item in space_res.items() if item[0] in analysis_names] 
                for analysis, analysis_res in analyses:       
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
            
                        # binned eccentricity vs other parameters relationships       
            
                        model_colors = {'Gauss':'blue','CSS':'orange','DoG':'green','Norm':'red'}
                                                
                        #model_symbols = {'Gauss':'^','CSS':'o','DoG':'v','Norm':'D'}
                        roi_colors = dd(lambda:'blue')
                        roi_colors['custom.V1']= 'black'
                        roi_colors['custom.V2']= 'red'
                        roi_colors['custom.V3']= 'pink'
            
                        fw_hmax_stats = dd(lambda:dd(list))
                        ecc_stats = dd(lambda:dd(list))
            
                        for roi in rois:
            
                            pl.figure(roi+' fw_hmax', figsize=(8, 6), frameon=False)
           
                            for model in subj_res['Processed Results']['Size (fwhmax)'].keys():                                
            
                                #model-specific alpha? or all models same alpha?
                                alpha_roi = roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh
                                
                                ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                fwhmax_model_roi = subj_res['Processed Results']['Size (fwhmax)'][model][alpha_roi]
                                rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                
                                ecc_sorted = np.argsort(ecc_model_roi)
                                split_ecc_bins = np.array_split(ecc_sorted, 10)
                               
                                for ecc_quantile in split_ecc_bins:
                                    fw_hmax_stats[roi][model].append(weightstats.DescrStatsW(fwhmax_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                                    ecc_stats[roi][model].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                       
                                WLS = LinearRegression()
                                WLS.fit(ecc_model_roi.reshape(-1, 1), fwhmax_model_roi, sample_weight=rsq_model_roi)
                                pl.plot([ss.mean for ss in ecc_stats[roi][model]],
                                        WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][model]]).reshape(-1, 1)),
                                        color=model_colors[model])
                                            
                                print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), fwhmax_model_roi, sample_weight=rsq_model_roi)))
            
                                pl.errorbar([ss.mean for ss in ecc_stats[roi][model]],
                                   [ss.mean for ss in fw_hmax_stats[roi][model]],
                                   yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in fw_hmax_stats[roi][model]]).T,
                                   xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][model]]).T,
                                   fmt='s', mfc=model_colors[model], mec='black', label=model, ecolor=model_colors[model])
            
                            pl.xlabel('Eccentricity (degrees)')
                            pl.ylabel(roi.replace('custom.','')+' pRF size (degrees)')
                            pl.legend(loc=0)
                            if save_figures:
                                pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                           roi.replace('custom.','')+'_fw-hmax.png', dpi=200, bbox_inches='tight')
                                
                        for model in subj_res['Processed Results']['Size (fwhmax)'].keys():
                            pl.figure(model+' fw_hmax', figsize=(8, 6), frameon=False)
                            for roi in rois:
                                #model-specific alpha? or all models same alpha?
                                alpha_roi = roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh
                                
                                ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                fwhmax_model_roi = subj_res['Processed Results']['Size (fwhmax)'][model][alpha_roi]
                                rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                
                                ecc_sorted = np.argsort(ecc_model_roi)
                                split_ecc_bins = np.array_split(ecc_sorted, 10)
                               
                                for ecc_quantile in split_ecc_bins:
                                    fw_hmax_stats[roi][model].append(weightstats.DescrStatsW(fwhmax_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                                    ecc_stats[roi][model].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                       
                                WLS = LinearRegression()
                                WLS.fit(ecc_model_roi.reshape(-1, 1), fwhmax_model_roi, sample_weight=rsq_model_roi)
                                pl.plot([ss.mean for ss in ecc_stats[roi][model]],
                                        WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][model]]).reshape(-1, 1)),
                                        color=roi_colors[roi])
                                            
                                print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), fwhmax_model_roi, sample_weight=rsq_model_roi)))
            
                                pl.errorbar([ss.mean for ss in ecc_stats[roi][model]],
                                   [ss.mean for ss in fw_hmax_stats[roi][model]],
                                   yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in fw_hmax_stats[roi][model]]).T,
                                   xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][model]]).T,
                                   fmt='s', mfc=roi_colors[roi], mec='black', label=roi.replace('custom.',''), ecolor=roi_colors[roi])
            
                            pl.xlabel('Eccentricity (degrees)')
                            pl.ylabel(model+' pRF size (degrees)')
                            pl.legend(loc=0)
                            if save_figures:
                                pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                           model+'_fw-hmax.png', dpi=200, bbox_inches='tight')

    def ecc_surround_roi_plots(self, rois, rsq_thresh, save_figures):
        
        pl.rcParams.update({'font.size': 16})
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                for analysis, analysis_res in space_res.items():       
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
            
                        # binned eccentricity vs other parameters relationships       
            
                        model_colors = {'Gauss':'blue','CSS':'orange','DoG':'green','Norm':'red'}
                                                
                        #model_symbols = {'Gauss':'^','CSS':'o','DoG':'v','Norm':'D'}
                        roi_colors = dd(lambda:'blue')
                        roi_colors['custom.V1']= 'black'
                        roi_colors['custom.V2']= 'red'
                        roi_colors['custom.V3']= 'pink'
            
                        fw_atmin_stats = dd(lambda:dd(list))
                        ecc_stats = dd(lambda:dd(list))
                        
                        #exclude surrounds sizes larger than this (no surround)
                        w_max=90
            
                        for roi in rois:
            
                            pl.figure(roi+' fw_atmin', figsize=(8, 6), frameon=False)
           
                            for model in subj_res['Processed Results']['Surround Size (fwatmin)'].keys():                                
            
                                #model-specific alpha? or all models same alpha?
                                alpha_roi = (roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh) * (subj_res['Processed Results']['Surround Size (fwatmin)'][model]<w_max)
                                
                                ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                fwatmin_model_roi = subj_res['Processed Results']['Surround Size (fwatmin)'][model][alpha_roi]
                                rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                
                                ecc_sorted = np.argsort(ecc_model_roi)
                                split_ecc_bins = np.array_split(ecc_sorted, 10)
                               
                                for ecc_quantile in split_ecc_bins:
                                    fw_atmin_stats[roi][model].append(weightstats.DescrStatsW(fwatmin_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                                    ecc_stats[roi][model].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                       
                                WLS = LinearRegression()
                                WLS.fit(ecc_model_roi.reshape(-1, 1), fwatmin_model_roi, sample_weight=rsq_model_roi)
                                pl.plot([ss.mean for ss in ecc_stats[roi][model]],
                                        WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][model]]).reshape(-1, 1)),
                                        color=model_colors[model])
                                            
                                print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), fwatmin_model_roi, sample_weight=rsq_model_roi)))
            
                                pl.errorbar([ss.mean for ss in ecc_stats[roi][model]],
                                   [ss.mean for ss in fw_atmin_stats[roi][model]],
                                   yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in fw_atmin_stats[roi][model]]).T,
                                   xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][model]]).T,
                                   fmt='s', mfc=model_colors[model], mec='black', label=model, ecolor=model_colors[model])
            
                            pl.xlabel('Eccentricity (degrees)')
                            pl.ylabel(roi.replace('custom.','')+' pRF Surround Size (degrees)')
                            pl.legend(loc=0)
                            if save_figures:
                                pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                           roi.replace('custom.','')+'_fw-atmin.png', dpi=200, bbox_inches='tight')
                                
                        for model in subj_res['Processed Results']['Surround Size (fwatmin)'].keys():
                            pl.figure(model+' fw_atmin', figsize=(8, 6), frameon=False)
                            for roi in rois:
                                #model-specific alpha? or all models same alpha?
                                alpha_roi = (roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh) * (subj_res['Processed Results']['Surround Size (fwatmin)'][model]<w_max)
                                
                                ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                fwatmin_model_roi = subj_res['Processed Results']['Surround Size (fwatmin)'][model][alpha_roi]
                                rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                
                                ecc_sorted = np.argsort(ecc_model_roi)
                                split_ecc_bins = np.array_split(ecc_sorted, 10)
                               
                                for ecc_quantile in split_ecc_bins:
                                    fw_atmin_stats[roi][model].append(weightstats.DescrStatsW(fwatmin_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                                    ecc_stats[roi][model].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                       
                                WLS = LinearRegression()
                                WLS.fit(ecc_model_roi.reshape(-1, 1), fwatmin_model_roi, sample_weight=rsq_model_roi)
                                pl.plot([ss.mean for ss in ecc_stats[roi][model]],
                                        WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][model]]).reshape(-1, 1)),
                                        color=roi_colors[roi])
                                            
                                print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), fwatmin_model_roi, sample_weight=rsq_model_roi)))
            
                                pl.errorbar([ss.mean for ss in ecc_stats[roi][model]],
                                   [ss.mean for ss in fw_atmin_stats[roi][model]],
                                   yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in fw_atmin_stats[roi][model]]).T,
                                   xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][model]]).T,
                                   fmt='s', mfc=roi_colors[roi], mec='black', label=roi.replace('custom.',''), ecolor=roi_colors[roi])
            
                            pl.xlabel('Eccentricity (degrees)')
                            pl.ylabel(model+' pRF Surround Size (degrees)')
                            pl.legend(loc=0)
                            if save_figures:
                                pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                           model+'_fw-atmin.png', dpi=200, bbox_inches='tight')            
            
            
    def ecc_css_exp_roi_plots(self, rois, rsq_thresh, save_figures):
        
        pl.rcParams.update({'font.size': 16})
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                for analysis, analysis_res in space_res.items():       
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
            
                        # binned eccentricity vs other parameters relationships       
            
                        roi_colors = dd(lambda:'blue')
                        roi_colors['custom.V1']= 'black'
                        roi_colors['custom.V2']= 'red'
                        roi_colors['custom.V3']= 'pink'
            
                        css_exp_stats = dd(lambda:dd(list))
                        ecc_stats = dd(lambda:dd(list))
                        
                        pl.figure('css_exp', figsize=(8, 6), frameon=False)
                        for roi in rois:

                            if 'CSS' in subj_res['Processed Results']['RSq'].keys():                                
                                model = 'CSS'
                                #model-specific alpha? or all models same alpha?
                                alpha_roi = (roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh)
                                
                                ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                css_exp_roi = subj_res['Processed Results']['CSS Exponent'][model][alpha_roi]
                                rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                
                                ecc_sorted = np.argsort(ecc_model_roi)
                                split_ecc_bins = np.array_split(ecc_sorted, 10)
                               
                                for ecc_quantile in split_ecc_bins:
                                    css_exp_stats[roi][model].append(weightstats.DescrStatsW(css_exp_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                                    ecc_stats[roi][model].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                          weights=rsq_model_roi[ecc_quantile]))
            
                       
                                # WLS = LinearRegression()
                                # WLS.fit(ecc_model_roi.reshape(-1, 1), css_exp_roi, sample_weight=rsq_model_roi)
                                # pl.plot([ss.mean for ss in ecc_stats[roi][model]],
                                #         WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][model]]).reshape(-1, 1)),
                                #         color=roi_colors[roi])
                                            
                                # print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), css_exp_roi, sample_weight=rsq_model_roi)))
            
                                pl.errorbar([ss.mean for ss in ecc_stats[roi][model]],
                                   [ss.mean for ss in css_exp_stats[roi][model]],
                                   yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in css_exp_stats[roi][model]]).T,
                                   xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][model]]).T,
                                   fmt='s', mfc=roi_colors[roi], mec='black', label=roi.replace('custom.',''), ecolor=roi_colors[roi])
            
                            pl.xlabel('Eccentricity (degrees)')
                            pl.ylabel('CSS Exponent')
                            pl.legend(loc=0)
                            if save_figures:
                                pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                           roi.replace('custom.','')+'_css-exp.png', dpi=200, bbox_inches='tight')            
            
    def ecc_norm_baselines_roi_plots(self, rois, rsq_thresh, save_figures, analysis_names='all'):
        
        pl.rcParams.update({'font.size': 16})
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                if analysis_names == 'all':
                    analyses = space_res.items()
                else:
                    analyses = [item for item in space_res.items() if item[0] in analysis_names] 
                for analysis, analysis_res in analyses:         
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
            
                        # binned eccentricity vs other parameters relationships       
            
                        roi_colors = dd(lambda:'blue')
                        roi_colors['custom.V1']= 'black'
                        roi_colors['custom.V2']= 'red'
                        roi_colors['custom.V3']= 'pink'
                        
                        params = {}
                        params['Norm Param. B'] = 'o'
                        params['Norm Param. D'] = 'o'
                        params['Ratio (B/D)'] = 'o'     
                        
                        
                        symbol={}
                        symbol['ABCD_100'] = 'o'
                        symbol['ACD_100'] = 's'
                        symbol['ABC_100'] = 'D'
            
                        norm_baselines_stats = dd(lambda:dd(list))
                        ecc_stats = dd(lambda:dd(list))                      
                        
                        for param in params:
                            pl.figure(analysis+param, figsize=(8, 6), frameon=False)
                            if 'Norm' in subj_res['Processed Results']['RSq'].keys():
                                model = 'Norm'
                                for roi in rois:
                                    
                                    #model-specific alpha? or all models same alpha?
                                    alpha_roi = (roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha'][model])>rsq_thresh)
                                    
                                    ecc_model_roi = subj_res['Processed Results']['Eccentricity'][model][alpha_roi]
                                    rsq_model_roi = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                    
                                    ecc_sorted = np.argsort(ecc_model_roi)
                                    split_ecc_bins = np.array_split(ecc_sorted, 8)
                                    
                                    norm_baselines_roi = subj_res['Processed Results'][param][model][alpha_roi]
                                   
                                    for ecc_quantile in split_ecc_bins:
                                        norm_baselines_stats[roi][param].append(weightstats.DescrStatsW(norm_baselines_roi[ecc_quantile],
                                                                                              weights=rsq_model_roi[ecc_quantile]))
                
                                        ecc_stats[roi][param].append(weightstats.DescrStatsW(ecc_model_roi[ecc_quantile],
                                                                                              weights=rsq_model_roi[ecc_quantile]))
                
                           
                                    # WLS = LinearRegression()
                                    # WLS.fit(ecc_model_roi.reshape(-1, 1), norm_baselines_roi, sample_weight=rsq_model_roi)
                                    # pl.plot([ss.mean for ss in ecc_stats[roi][param]],
                                    #          WLS.predict(np.array([ss.mean for ss in ecc_stats[roi][param]]).reshape(-1, 1)),
                                    #          color=roi_colors[roi])
                                                
                                    # print(roi+" "+model+" "+str(WLS.score(ecc_model_roi.reshape(-1, 1), norm_baselines_roi, sample_weight=rsq_model_roi)))
                
                                    pl.errorbar([ss.mean for ss in ecc_stats[roi][param]],
                                       [ss.mean for ss in norm_baselines_stats[roi][param]],
                                       yerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in norm_baselines_stats[roi][param]]).T,
                                       xerr=np.array([np.abs(ss.zconfint_mean(alpha=0.05)-ss.mean) for ss in ecc_stats[roi][param]]).T,
                                       fmt='s', mfc=roi_colors[roi], mec='black', label=analysis.replace('_100','')+' '+roi.replace('custom.',''), ecolor=roi_colors[roi])
            
                                pl.xlabel('Eccentricity (degrees)')
                                pl.ylabel(param)
                                pl.legend(loc=0)
                                if save_figures:
                                    pl.savefig('/Users/marcoaqil/PRFMapping/Figures/'+subj+'_'+
                                               param.replace("/","").replace('.','').replace(' ','_')+'.png', dpi=200, bbox_inches='tight')
                                    
                                    
    def rsq_roi_plots(self, rois, rsq_thresh, save_figures, analysis_names='all', noise_ceiling=None):
        bar_position = 0
        last_bar_position = dd(lambda:0)
        x_ticks=[]
        x_labels=[]
        pl.rcParams.update({'font.size': 16})
        pl.rc('figure', facecolor='w')
        for space, space_res in self.main_dict.items():
            if 'fs' in space:
                if analysis_names == 'all':
                    analyses = space_res.items()
                else:
                    analyses = [item for item in space_res.items() if item[0] in analysis_names] 
                for analysis, analysis_res in analyses:        
                    for subj, subj_res in analysis_res.items():
                        print(space+" "+analysis+" "+subj)
            
                        # binned eccentricity vs other parameters relationships       
            
                        model_colors = {'Gauss':'blue','CSS':'orange','DoG':'green','Norm':'red'}
                        

                        for roi in rois:
                            bar_position=last_bar_position[roi]+0.1
                            pl.figure(roi+'RSq', figsize=(8, 6), frameon=False)
                            pl.ylabel(roi.replace('custom.','')+' Mean RSq')
                            alpha_roi = roi_mask(self.idx_rois[subj][roi], subj_res['Processed Results']['Alpha']['all'])>rsq_thresh
                            model_list = [k for k in subj_res['Processed Results']['RSq'].keys()]
                            
                            for model in model_list:                                
                                model_rsq = subj_res['Processed Results']['RSq'][model][alpha_roi]
                                # if noise_ceiling is not None:
                                #     model_rsq /= noise_ceiling[alpha_roi]
                                    
                                bar_height = np.mean(model_rsq)
                                bar_err = sem(model_rsq)
                                pl.bar(bar_position, bar_height, width=0.1, yerr=bar_err, color=model_colors[model],edgecolor='black')
                                x_ticks.append(bar_position)
                                if 'ABCD' in analysis:
                                    x_labels.append(analysis.replace('_100','').replace('ABCD_','')+'\n'+model)
                                else:
                                    x_labels.append(analysis.replace('_100','')+'\n'+model)
                                bar_position += 0.1
                                
                            if noise_ceiling is not None:
                                bar_height=np.mean(noise_ceiling[alpha_roi])
                                bar_err = sem(noise_ceiling[alpha_roi])
                                pl.bar(bar_position, bar_height, width=0.1, yerr=bar_err, color='grey',edgecolor='black')
                                x_ticks.append(bar_position)
                                x_labels.append('NC')
                                bar_position += 0.1

                            last_bar_position[roi] = bar_position
                            pl.xticks(x_ticks,x_labels)

                             
                            if 'CSS' in model_list and 'DoG' in model_list:
                                surround_voxels = subj_res['Processed Results']['RSq']['DoG'][alpha_roi]>subj_res['Processed Results']['RSq']['Gauss'][alpha_roi]
                                nonlinear_voxels = subj_res['Processed Results']['RSq']['CSS'][alpha_roi]>subj_res['Processed Results']['RSq']['Gauss'][alpha_roi]
                                
                                print(analysis+' '+roi)
                                print(f"{roi} voxels above {rsq_thresh} threshold within stimulus eccentricity: {np.sum(alpha_roi)} out of {len(self.idx_rois[subj][roi])}")
                                
                                print(f"Norm-CSS in {roi} surround voxels: {ks_2samp(subj_res['Processed Results']['RSq']['Norm'][alpha_roi][surround_voxels],subj_res['Processed Results']['RSq']['CSS'][alpha_roi][surround_voxels])}")
                                print(f"Norm-DoG in {roi} nonlinear voxels: {ks_2samp(subj_res['Processed Results']['RSq']['Norm'][alpha_roi][nonlinear_voxels],subj_res['Processed Results']['RSq']['DoG'][alpha_roi][nonlinear_voxels])}")
                                
                                norm_css_surrvox = subj_res['Processed Results']['RSq']['Norm'][alpha_roi][surround_voxels]-subj_res['Processed Results']['RSq']['CSS'][alpha_roi][surround_voxels]
                                norm_dog_nonlvox = subj_res['Processed Results']['RSq']['Norm'][alpha_roi][nonlinear_voxels]-subj_res['Processed Results']['RSq']['DoG'][alpha_roi][nonlinear_voxels]
                                norm_css_nonlvox = subj_res['Processed Results']['RSq']['Norm'][alpha_roi][nonlinear_voxels]-subj_res['Processed Results']['RSq']['CSS'][alpha_roi][nonlinear_voxels]
                                norm_dog_surrvox = subj_res['Processed Results']['RSq']['Norm'][alpha_roi][surround_voxels]-subj_res['Processed Results']['RSq']['DoG'][alpha_roi][surround_voxels]
                                
                                # if noise_ceiling is not None:
                                #     norm_css_surrvox /= noise_ceiling[alpha_roi][surround_voxels]
                                #     norm_dog_nonlvox /= noise_ceiling[alpha_roi][nonlinear_voxels]
                                #     norm_css_nonlvox /= noise_ceiling[alpha_roi][nonlinear_voxels]
                                #     norm_dog_surrvox /= noise_ceiling[alpha_roi][surround_voxels]
                                    
                                print(f"Norm-CSS in {roi} surround voxels: {ttest_1samp(norm_css_surrvox,0)}")
                                print(f"Norm-DoG in {roi} nonlinear voxels: {ttest_1samp(norm_dog_nonlvox,0)}")
                                
                                print(f"Norm-CSS in {roi} surround voxels: {wilcoxon(norm_css_surrvox)}")
                                print(f"Norm-DoG in {roi} nonlinear voxels: {wilcoxon(norm_dog_nonlvox)}")
                                                                              
                                print(f"Norm-CSS in {roi} surround voxels: {np.mean(norm_css_surrvox)}")
                                print(f"Norm-DoG in {roi} nonlinear voxels: {np.mean(norm_dog_nonlvox)}")
                                if len(analysis_names)<5:
                                    fig, axs = pl.subplots(2, 2, sharey=True, sharex=True)
                                    fig.suptitle(roi.replace('custom.',''))
                                    axs[0,0].set_xlabel('Norm-CSS')
                                    axs[0,0].set_ylabel('Number of vertices')
                                    axs[0,1].set_xlabel('Norm-CSS') 
                                    axs[0,0].set_title('Surround vertices')
                                    axs[0,1].set_title('Nonlinear vertices')
                                    
                                    h1 = axs[0,0].hist(norm_css_surrvox,bins=100)
                                    h2 = axs[0,1].hist(norm_css_nonlvox,bins=100)
                                    

                                    axs[1,0].set_xlabel('Norm-DoG')
                                    axs[1,0].set_ylabel('Number of vertices')
                                    axs[1,1].set_xlabel('Norm-DoG') 
                                    
                                    h3 = axs[1,0].hist(norm_dog_surrvox,bins=100)
                                    h4 = axs[1,1].hist(norm_dog_nonlvox,bins=100)
                                    
                                    height = 1+int(np.max([h1[0].max(),h2[0].max(), h3[0].max(), h4[0].max()]))
                                    
                                    axs[0,0].plot(np.zeros(height), np.arange(height), c='black', linestyle='--')   
                                    axs[0,1].plot(np.zeros(height), np.arange(height), c='black', linestyle='--')                               
                                    axs[1,0].plot(np.zeros(height), np.arange(height), c='black', linestyle='--')   
                                    axs[1,1].plot(np.zeros(height), np.arange(height), c='black', linestyle='--')                                

                            print('---------------')
                        print('\n')
                            
                               
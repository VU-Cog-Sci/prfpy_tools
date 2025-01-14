#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov  2 11:51:11 2019

@author: marcoaqil
"""


import os
import numpy as np
from pathlib import Path
opj = os.path.join
import yaml
import sys
from datetime import datetime
from shutil import copyfile as cp


results_path = sys.argv[1]
subjects = sys.argv[2]


for subj_ses in subjects.split(','):
    subj = subj_ses.split('_')[0]
    analysis_settings_files = sorted(Path(results_path).glob(f"{subj_ses}_analysis_settings.yml"))

    for analysis_settings in analysis_settings_files:

        with open(str(analysis_settings)) as f:
            analysis_info = yaml.safe_load(f)
        
        session = analysis_info["session"]
        
        # note that screenshot paths and task names should be in the same order
        n_pix = analysis_info["n_pix"]
        discard_volumes = analysis_info["discard_volumes"]
        screenshot_paths = analysis_info["screenshot_paths"]
        screen_size_cm = analysis_info["screen_size_cm"]
        screen_distance_cm = analysis_info["screen_distance_cm"]
        TR = analysis_info["TR"]
        task_names = analysis_info["task_names"]
        data_path = analysis_info["data_path"]
        fitting_space = analysis_info["fitting_space"]
        save_raw_timecourse = analysis_info["save_raw_timecourse"]
        
        window_length = analysis_info["window_length"]
        n_jobs = analysis_info["n_jobs"]
        hrf = analysis_info["hrf"]
        verbose = analysis_info["verbose"]
        rsq_threshold = analysis_info["rsq_threshold"]
        models_to_fit = analysis_info["models_to_fit"]
        n_batches = analysis_info["n_batches"]
        grid_fit_hrf_norm = analysis_info["grid_fit_hrf_norm"]
        grid_fit_hrf_gauss = analysis_info["grid_fit_hrf_gauss"]
        use_previous_gaussian_fitter_hrf = analysis_info["use_previous_gaussian_fitter_hrf"]
        crossvalidate = analysis_info["crossvalidate"]

        if "norm" in models_to_fit and "norm_model_variant" in analysis_info:
            norm_model_variant = analysis_info["norm_model_variant"]
        else:
            norm_model_variant = ["abcd"]
            
        save_noise_ceiling = analysis_info["save_noise_ceiling"]
        
        dm_edges_clipping = analysis_info["dm_edges_clipping"]
        min_percent_var = analysis_info["min_percent_var"]
        
        n_chunks = analysis_info["n_chunks"]
        refit_mode = analysis_info["refit_mode"].lower()
        
        data_path = opj(data_path,'prfpy')
        
        analysis_time = analysis_info["analysis_time"]
        
        previous_analysis_time = analysis_info["previous_analysis_time"]
        previous_analysis_refit_mode = analysis_info["previous_analysis_refit_mode"]
        
        dog_grid = analysis_info["dog_grid"]
        css_grid = analysis_info["css_grid"]
        
        if 'scratch' in data_path:
            replacer = 'home'
        else:
            replacer = data_path.split(os.path.sep)[1]
        
        
        if refit_mode == previous_analysis_refit_mode and refit_mode!="overwrite":
            analysis_time = previous_analysis_time
        
        #first check if iteration was completed
        unfinished_chunks=[]
        # for chunk_nr in range(n_chunks):
        #     print(opj(data_path, f"{subj}_{session}_iterparams-{models_to_fit[-1].lower()}_space-{fitting_space}{chunk_nr}.npy"))
                                
        if refit_mode in ["skip", "overwrite"]:
            last_model = models_to_fit[-1].lower()
            if last_model == 'norm':
                last_model += norm_model_variant[-1]
            
            exists = np.array([os.path.exists(opj(data_path, f"{subj}_{session}_iterparams-{last_model}_space-{fitting_space}{chunk_nr}.npy")) for chunk_nr in range(n_chunks)])
            finished_chunks = np.where(exists)[0]
            if np.any(exists==False):
                for value in np.where(exists==False)[0]:
                    unfinished_chunks.append(value)
        
        
        else:
            finished_chunks = np.arange(n_chunks)
        
        if refit_mode in ["iterate", "overwrite"] and "--force_harvest" not in sys.argv:
            for model in models_to_fit:
                model=model.lower()
                if model == 'norm':
                    for variant in norm_model_variant:
                        last_edited = np.array([(datetime.fromtimestamp(os.stat(opj(data_path,
                                                                        f"{subj}_{session}_iterparams-{model}{variant}_space-{fitting_space}{chunk_nr}.npy")).st_mtime)) < datetime(\
                                                                        int(analysis_time.split('-')[0]),
                                                                        int(analysis_time.split('-')[1]),
                                                                        int(analysis_time.split('-')[2]),
                                                                        int(analysis_time.split('-')[3]),
                                                                        int(analysis_time.split('-')[4]),
                                                                        int(analysis_time.split('-')[5]), 0) for chunk_nr in finished_chunks])
                
                
                        if np.any(last_edited):
                
                            print(f"Fitting of {model} {variant} model has not been completed")
                            for value in np.where(last_edited)[0]:
                                unfinished_chunks.append(value)
                
                                filepath = opj(data_path,f"{subj}_{session}_iterparams-{model}{variant}_space-{fitting_space}"+str(value)+".npy")
                                if refit_mode == "overwrite":
                                    #print("Renaming unfinished files to _old, so can run next in skip mode.")
                                    os.rename(filepath,filepath[:-4]+"_old.npy")
                else:
                    last_edited = np.array([(datetime.fromtimestamp(os.stat(opj(data_path,
                                                                        f"{subj}_{session}_iterparams-{model}_space-{fitting_space}{chunk_nr}.npy")).st_mtime)) < datetime(\
                                                                        int(analysis_time.split('-')[0]),
                                                                        int(analysis_time.split('-')[1]),
                                                                        int(analysis_time.split('-')[2]),
                                                                        int(analysis_time.split('-')[3]),
                                                                        int(analysis_time.split('-')[4]),
                                                                        int(analysis_time.split('-')[5]), 0) for chunk_nr in finished_chunks])
                
                
                    if np.any(last_edited):
            
                        print(f"Fitting of {model} model has not been completed")
                        for value in np.where(last_edited)[0]:
                            unfinished_chunks.append(value)
            
                            filepath = opj(data_path,f"{subj}_{session}_iterparams-{model}_space-{fitting_space}"+str(value)+".npy")
                            if refit_mode == "overwrite":
                                #print("Renaming unfinished files to _old, so can run next in skip mode.")
                                os.rename(filepath,filepath[:-4]+"_old.npy")
        
        
        
        if len(unfinished_chunks)>0 and "--force_harvest" not in sys.argv:
            print("Make sure to be in skip or iterate mode first! Then run:")
            str_resub='"( '
            for value in np.unique(unfinished_chunks):
                str_resub+=(str(value)+' ')
            str_resub+=')"'
            print(f"python array_submit_prf_fit_only.py {subj} {session} $analysis_redo_settings {str_resub}")
            
        
            print("harvest not completed. resubmit chunks.")
            continue

        order = np.load(opj(data_path, f"{subj}_{session}_order_space-{fitting_space}.npy"))

        #
        grid_models = ["gauss", "norm"]
        if dog_grid:
            grid_models.append("dog")
        if css_grid:
            grid_models.append("css")
        
        for model in models_to_fit:
            model = model.lower()

            if model == 'norm':
                for variant in norm_model_variant:

                    if model in grid_models and refit_mode != "iterate":
                        if f"norm{variant}_gridparams_path" not in analysis_info and f"norm{variant}_iterparams_path" not in analysis_info:
                            grid_path = opj(data_path, f"{subj}_{session}_gridparams-{model}{variant}_space-{fitting_space}")
                            grid_result = np.concatenate(tuple([np.load(grid_path+str(chunk_nr)+".npy") for chunk_nr in range(n_chunks)]), axis=0)
                    
                            grid_path+=analysis_time
                    
                            grid_result[order] = np.copy(grid_result)
                    
                            np.save(grid_path.replace(grid_path.split(os.path.sep)[1], replacer), grid_result) 
                
                    iter_path = opj(data_path, f"{subj}_{session}_iterparams-{model}{variant}_space-{fitting_space}")
                
                    model_result = np.concatenate(tuple([np.load(iter_path+str(chunk_nr)+".npy") for chunk_nr in range(n_chunks)]), axis=0)
                
                    iter_path+=analysis_time
                
                    model_result[order] = np.copy(model_result)
                
                    np.save(iter_path.replace(iter_path.split(os.path.sep)[1], replacer), model_result)
            else:
                if model in grid_models and refit_mode != "iterate":
                    if f"{model}_gridparams_path" not in analysis_info and f"{model}_iterparams_path" not in analysis_info:
                        grid_path = opj(data_path, f"{subj}_{session}_gridparams-{model}_space-{fitting_space}")
                        grid_result = np.concatenate(tuple([np.load(grid_path+str(chunk_nr)+".npy") for chunk_nr in range(n_chunks)]), axis=0)
                
                        grid_path+=analysis_time
                
                        grid_result[order] = np.copy(grid_result)
                
                        np.save(grid_path.replace(grid_path.split(os.path.sep)[1], replacer), grid_result) 
            
                iter_path = opj(data_path, f"{subj}_{session}_iterparams-{model}_space-{fitting_space}")
            
                model_result = np.concatenate(tuple([np.load(iter_path+str(chunk_nr)+".npy") for chunk_nr in range(n_chunks)]), axis=0)
            
                iter_path+=analysis_time
            
                model_result[order] = np.copy(model_result)
            
                np.save(iter_path.replace(iter_path.split(os.path.sep)[1], replacer), model_result)
        
        #mask is saved in original order so only need to copypaste
        mask_path=opj(data_path,  f"{subj}_{session}_mask_space-{fitting_space}.npy")
        cp(mask_path, mask_path.replace(mask_path.split(os.path.sep)[1], replacer).replace('.npy',analysis_time+'.npy'))
        
        #save noise ceiling
        if save_noise_ceiling:
            nc_path = opj(data_path,f"{subj}_{session}_noise-ceiling_space-{fitting_space}.npy")
            cp(nc_path, nc_path.replace(nc_path.split(os.path.sep)[1], replacer).replace('.npy',analysis_time+'.npy'))
        
        
        if "--grab" in sys.argv:
            print("Grabbing timecourse for this analysis...")
        
            #these are saved in randomized order, so must take into account. like for models above
            tc_path=opj(data_path,  f"{subj}_{session}_timecourse_space-{fitting_space}.npy")
            tc = np.load(tc_path)
            tc_ordered = np.zeros_like(tc)
            tc_ordered[order] = np.copy(tc)
            np.save(tc_path.replace(tc_path.split(os.path.sep)[1], replacer).replace('.npy',analysis_time+'.npy'), tc_ordered)
            
                
            if crossvalidate:
                tc_test_path=opj(data_path,  f"{subj}_{session}_timecourse-test_space-{fitting_space}.npy")
                tc_test = np.load(tc_test_path)
                tc_test_ordered = np.zeros_like(tc_test)
                tc_test_ordered[order] = np.copy(tc_test)
                np.save(tc_test_path.replace(tc_test_path.split(os.path.sep)[1], replacer).replace('.npy',analysis_time+'.npy'), tc_test_ordered)
        
        
        analysis_settings=str(analysis_settings)
        cp(analysis_settings, analysis_settings.replace(analysis_settings.split(os.path.sep)[1], replacer).replace('.yml',analysis_time+'.yml'))
        print(f"harvest subj {subj}_{session} completed")


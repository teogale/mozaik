#!/home/jan/virt_env/virt_env/hdf5/bin/python
import sys
sys.path.append('/home/jan/projects/mozaik-random_data_access/')
import matplotlib
import time
from mozaik.framework.experiment import MeasureOrientationTuningFullfield, MeasureSpontaneousActivity, MeasureNaturalImagesWithEyeMovement
from pyNN import nest as sim
from mozaik.models.model import JensModel
from mozaik.framework.experiment_controller import run_experiments, setup_experiments, setup_logging
from mozaik.visualization.plotting import GSynPlot,RasterPlot,VmPlot,CyclicTuningCurvePlot,OverviewPlot, ConductanceSignalListPlot, RetinalInputMovie, ActivityMovie, PerNeuronValuePlot
from mozaik.analysis.analysis import AveragedOrientationTuning,  GSTA, Precision, PeriodicTuningCurvePreferenceAndSelectivity_VectorAverage
from mozaik.analysis.technical import NeuronAnnotationsToPerNeuronValues
from mozaik.visualization.Kremkow_plots import Figure2
from mozaik.storage.datastore import Hdf5DataStore,PickledDataStore
from NeuroTools.parameters import ParameterSet
from mozaik.storage.queries import *


t0 = time.time()


if False:
    params = setup_experiments('FFI',sim)    
    jens_model = JensModel(sim,params)
    
    experiment_list =   [
                           #Spontaneous Activity 
                           MeasureSpontaneousActivity(jens_model,duration=70*7),
                           
                           # LONG
                           #MeasureOrientationTuningFullfield(jens_model,num_orientations=12,spatial_frequency=0.8,temporal_frequency=2,grating_duration=2*148*7,num_trials=10),
                           
                           # MEDIUM ORIENTATION TUNING
                           #MeasureOrientationTuningFullfield(jens_model,num_orientations=12,spatial_frequency=0.8,temporal_frequency=2,grating_duration=148*7,num_trials=4),
                           
                           # SHORT ORIENTATION TUNING
                           #MeasureOrientationTuningFullfield(jens_model,num_orientations=6,spatial_frequency=0.8,temporal_frequency=2,grating_duration=148*7,num_trials=1),
                           
                           #SINGLE STIMULUS
                           MeasureOrientationTuningFullfield(jens_model,num_orientations=1,spatial_frequency=0.8,temporal_frequency=2,grating_duration=148*7,num_trials=2),
                        ]

    data_store = run_experiments(jens_model,experiment_list)
else:
    setup_logging()
    data_store = PickledDataStore(load=True,parameters=ParameterSet({'root_directory':'A'}))
    print 'Loaded data store'

import resource
print "Current memory usage: %iMB" % (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024))

t1 = time.time()
print 'Loading lasted:' , t1-t0

AveragedOrientationTuning(data_store,ParameterSet({})).analyse()
GSTA(data_store,ParameterSet({'neurons' : [0], 'length' : 50.0 }),tags=['GSTA1']).analyse()
Precision(select_result_sheet_query(data_store,"V1_Exc"),ParameterSet({'neurons' : [0], 'bin_length' : 10.0 })).analyse()

PeriodicTuningCurvePreferenceAndSelectivity_VectorAverage(data_store,ParameterSet({})).analyse()
NeuronAnnotationsToPerNeuronValues(data_store,ParameterSet({})).analyse()

OverviewPlot(data_store,ParameterSet({'sheet_name' : 'V1_Exc', 'neuron' : 0, 'sheet_activity' : {}})).plot()
OverviewPlot(data_store,ParameterSet({'sheet_name' : 'V1_Inh', 'neuron' : 0, 'sheet_activity' : {}})).plot()
OverviewPlot(data_store,ParameterSet({'sheet_name' : 'X_ON', 'neuron' : 0, 'sheet_activity' : {}})).plot()
OverviewPlot(data_store,ParameterSet({'sheet_name' : 'X_OFF', 'neuron' : 0, 'sheet_activity' : {}})).plot()
Figure2(data_store,ParameterSet({'sheet_name' : 'V1_Exc'})).plot()

PerNeuronValuePlot(analysis_data_structure_parameter_filter_query(data_store,'PerNeuronValue',value_name='phase preference'),ParameterSet({})).plot()
PerNeuronValuePlot(analysis_data_structure_parameter_filter_query(data_store,'PerNeuronValue',value_name='LGNAfferentPhase'),ParameterSet({})).plot()

#PerNeuronValuePlot(analysis_data_structure_parameter_filter_query(data_store,'PerNeuronValue',value_name='orientation preference'),ParameterSet({})).plot()
#PerNeuronValuePlot(analysis_data_structure_parameter_filter_query(data_store,'PerNeuronValue',value_name='LGNAfferentOrientation'),ParameterSet({})).plot()
CyclicTuningCurvePlot(data_store,ParameterSet({'tuning_curve_name' : 'CyclicTuningCurve', 'neuron': 0, 'sheet_name' : 'V1_Exc'})).plot()

#RetinalInputMovie(data_store,ParameterSet({'frame_rate': 10})).plot()
import pylab
pylab.show()

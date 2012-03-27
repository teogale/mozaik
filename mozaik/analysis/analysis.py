"""
This module contains the Mozaik analysis interface and implementation of various analysis algorithms
"""
import pylab
import numpy 
import quantities as qt
import mozaik.tools.units as munits
from mozaik.stimuli.stimulus_generator import colapse, StimulusTaxonomy, parse_stimuls_id
from mozaik.analysis.analysis_data_structures import CyclicTuningCurve,TuningCurve, ConductanceSignalList , AnalogSignalList, PerNeuronValue
from mozaik.analysis.analysis_helper_functions import time_histogram_across_trials
from mozaik.framework.interfaces import MozaikParametrizeObject
from NeuroTools.parameters import ParameterSet
from mozaik.storage.queries import select_stimuli_type_query,select_result_sheet_query, partition_by_stimulus_paramter_query
from neo.core.analogsignal import AnalogSignal
from NeuroTools import signals

class Analysis(MozaikParametrizeObject):
    """
    Analysis encapsulates analysis algorithms. 
    The interface is extremely simple: it only requires the definition of analysis function
    which when called performs the actually analysis
    
    It is assumed that this function retrieves its own data from DataStore that is supplied in the self.datastore
    parameter. Also it is assumed to include self.tags as the tags for all AnalysisDataStructure that
    it creates. See description of self.tags in AnalysisDataStructure
    
    Args:
        datastore (DataStoreView): the datastore from which to pull data.
        parameters (ParameterSet): the parameter set
        tags (list(str)): tags to attach to the AnalysisDataStructures generated by the analysis
    
    """
    
    def __init__(self,datastore,parameters,tags=[]):
        MozaikParametrizeObject.__init__(self,parameters)
        self.datastore = datastore
        self.tags = tags

    def analyse(self):
        """
        """
        raise NotImplementedError
        pass
        

class AveragedOrientationTuning(Analysis):
      """
      This analysis takes all recordings with FullfieldDriftingSinusoidalGrating 
      stimulus. It averages the trials and creates tuning curves with respect to the 
      orientation parameter. Thus for each combination of the other stimulus parameters
      a tuning curve is created. 
      """
      def analyse(self):
            print 'Starting OrientationTuning analysis'
            dsv = select_stimuli_type_query(self.datastore,'FullfieldDriftingSinusoidalGrating')

            for sheet in dsv.sheets():
                dsv1 = select_result_sheet_query(dsv,sheet)
                segs = dsv1.get_segments()
                st = dsv1.get_stimuli()
                # transform spike trains due to stimuly to mean_rates
                mean_rates = [numpy.array(s.mean_rates())  for s in segs]
                # collapse against all parameters other then orientation
                (mean_rates,s) = colapse(mean_rates,st,parameter_indexes=[8])
                # take a sum of each 
                def _mean(a):
                    l = len(a)
                    return sum(a)/l
                mean_rates = [_mean(a) for a in mean_rates]
                
                #JAHACK make sure that mean_rates() return spikes per second
                units = munits.spike / qt.s
                print 'Adding CyclicTuningCurve to datastore'
                self.datastore.full_datastore.add_analysis_result(CyclicTuningCurve(numpy.pi,mean_rates,s,9,sheet,'Response',units,tags=self.tags),sheet_name=sheet)

class PeriodicTuningCurvePreferenceAndSelectivity_VectorAverage(Analysis):
      """
      This analysis takes all cyclic tuning curves.
      
      For each parametrization of tuning_curves it creates a PerNeuronVector holding the
      preference of the tuning curve for all neurons for which data were supplied.
      """
      def analyse(self):
            print 'Starting Orientation Preference analysis'
            for sheet in self.datastore.sheets():
                # get all the cyclic tuning curves 
                self.tuning_curves = self.datastore.get_analysis_result('CyclicTuningCurve',sheet_name=sheet)
                for tc in self.tuning_curves:
                    d = tc.to_dictonary_of_tc_parametrization()
                    result_dict = {}
                    for k in  d:
                        x = 0
                        y = 0 
                        n = 0
                        g,h = d[k]
                        for v,p in zip(g,h):
                            xx =  numpy.cos(p / tc.period * 2 * numpy.pi) * v   
                            yy =  numpy.sin(p / tc.period * 2 * numpy.pi) * v
                            x  =  x + xx
                            y  =  y + yy
                            n = n + numpy.sqrt(numpy.power(xx,2) + numpy.power(yy,2))
                        sel = numpy.sqrt(numpy.power(x,2) + numpy.power(y,2)) / n
                        pref = numpy.arccos(x/(numpy.sqrt(numpy.power(x,2) + numpy.power(y,2))))
                        print 'Adding PerNeuronValue to datastore'
                        self.datastore.full_datastore.add_analysis_result(PerNeuronValue(pref, StimulusTaxonomy[parse_stimuls_id(k).name][tc.parameter_index] + ' preference', qt.rad, sheet, tags=self.tags),sheet_name=sheet)
                        self.datastore.full_datastore.add_analysis_result(PerNeuronValue(sel, StimulusTaxonomy[parse_stimuls_id(k).name][tc.parameter_index] + ' selectivity', qt.dimensionless , sheet, tags=self.tags),sheet_name=sheet)
                                
                        


class GSTA(Analysis):
      """
      Computes conductance spike triggered average
      
      Note that it does not assume that spikes are aligned with the conductance sampling rate
      and will pick the bin in which the given spike falls (within the conductance sampling rate binning)
      as the center of the conductance vector that is included in the STA
      """
      
      required_parameters = ParameterSet({
        'length': float,  # length (in ms time) how long before and after spike to compute the GSTA
                          # it will be rounded down to fit the sampling frequency
        'neurons' : list, #the list of neuron indexes for which to compute the 
      })

      
      def analyse(self):
            print 'Starting Spike Triggered Analysis of Conductances'
            
            dsv = self.datastore
            for sheet in dsv.sheets():
                dsv1 = select_result_sheet_query(dsv,sheet)
                st = dsv1.get_stimuli()
                segs = dsv1.get_segments()
                
                sp = [s.spiketrains for s in segs]
                g_e = [s.get_esyn() for s in segs]
                g_i = [s.get_isyn() for s in segs]

                asl_e = []
                asl_i = []
                for n in self.parameters.neurons:
                    asl_e.append(self.do_gsta(g_e,sp,n))
                    asl_i.append(self.do_gsta(g_i,sp,n))
                self.datastore.full_datastore.add_analysis_result(ConductanceSignalList(asl_e,asl_i,sheet,self.parameters.neurons,tags=self.tags),sheet_name=sheet)
                
                
      def do_gsta(self,analog_signal,sp,n):
          dt = analog_signal[0].sampling_period
          gstal = int(self.parameters.length/dt)
          gsta = numpy.zeros(2*gstal+1,) 
          count = 0
          for (ans,spike) in zip(analog_signal,sp):
              for time in spike[n]:
                  if time > ans.t_start  and time < ans.t_stop:
                     idx = int((time - ans.t_start)/dt)
                     if idx - gstal > 0 and (idx + gstal+1) <= len(ans[:,n]):
                        gsta = gsta +  ans[idx-gstal:idx+gstal+1,n].flatten().magnitude
                        count +=1
          if count == 0:
             count = 1
          gsta = gsta/count
          gsta = gsta * analog_signal[0].units
          
          return AnalogSignal(gsta, t_start=-gstal*dt,sampling_period=dt,units=analog_signal[0].units)
          
           
          
          
class Precision(Analysis):
      """
      Computes the precision as the autocorrelation between the PSTH of different trials
      """
      
      required_parameters = ParameterSet({
        'neurons' : list, #the list of neuron indexes for which to compute the 
        'bin_length' : float, #(ms) the size of bin to construct the PSTH from
      })
      
      def analyse(self):
            print 'Starting Precision Analysis'
            dsv = self.datastore
            for sheet in dsv.sheets():
                dsv1 = select_result_sheet_query(dsv,sheet)
                dsvs = partition_by_stimulus_paramter_query(dsv1,7)
                
                for dsv in dsvs:
                    sl = [s.spiketrains for s in dsv.get_segments()]
                    t_start = sl[0][0].t_start
                    t_stop =  sl[0][0].t_stop
                    duration = t_stop-t_start
                    
                    hist = time_histogram_across_trials(sl,self.parameters.bin_length)
                    al = []
                    for n in self.parameters.neurons:
                        ac = numpy.correlate(hist[n], hist[n], mode='full')
                        if numpy.sum(numpy.power(hist[n],2)) != 0:
                            ac = ac / numpy.sum(numpy.power(hist[n],2))
                        al.append(AnalogSignal(ac, t_start=-duration,t_stop=duration-self.parameters.bin_length*t_start.units,sampling_period=self.parameters.bin_length*qt.ms,units=qt.dimensionless))
                   
                    print 'Adding AnalogSignalList', sheet
                    self.datastore.full_datastore.add_analysis_result(AnalogSignalList(al,sheet,self.parameters.neurons,'time','autocorrelation',qt.ms,qt.dimensionless,tags=self.tags),sheet_name=sheet)    
                        

from nipype.interfaces.base import BaseInterface, traits, BaseInterfaceInputSpec, TraitedSpec
from nipype.interfaces.semtools import BRAINSResample
import os
from training import image_data
from sklearn.externals import joblib
from predict import image_file_from_array_with_reference_image_file


def run_resample(in_file, ref_file, transform, out_file, interpolation_mode='Linear', pixel_type='float',
                 inverse_transform=True):
    resample = BRAINSResample()
    resample.inputs.inputVolume = in_file
    resample.inputs.warpTransform = transform
    resample.inputs.pixelType = pixel_type
    resample.inputs.interpolationMode = interpolation_mode
    resample.inputs.outputVolume = os.path.abspath(out_file)
    resample.inputs.referenceVolume = ref_file
    resample.inputs.inverseTransform = inverse_transform
    result = resample.run()
    return result.outputs.outputVolume


class CollectFeatureFilesInputSpec(BaseInterfaceInputSpec):
    rho = traits.File(exists=True)
    phi = traits.File(exists=True)
    theta = traits.File(exists=True)
    posterior_files = traits.Dict(desc="Dictionary of posterior probabilities")
    reference_file = traits.File(exists=True)
    transform_file = traits.File(exists=True)
    inverse_transform = traits.Bool(True, desc="if true, inverse transform will be used", use_default=True)


class CollectFeatureFilesOutputSpec(TraitedSpec):
    feature_files = traits.Dict(desc="Output dictionary of feature files")


class CollectFeatureFiles(BaseInterface):
    input_spec = CollectFeatureFilesInputSpec
    output_spec = CollectFeatureFilesOutputSpec
    feature_files = []

    def _run_interface(self, runtime):
        self.feature_files = self.combine_files()
        self.feature_files = self.resample_images_for_features(self.feature_files, self.inputs.reference_file,
                                                               self.inputs.transform_file)
        return runtime

    @staticmethod
    def _get_dict_name(filename):
        return os.path.basename(filename).split(".")[0]

    def combine_files(self):
        feature_files = [self.inputs.rho, self.inputs.phi, self.inputs.theta] + self.inputs.posterior_files.values
        return feature_files

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["feature_files"] = self._list_resampled_feature_files()
        return outputs

    def _list_resampled_feature_files(self):
        outputs = dict()
        for _file in self.feature_files:
            basename = os.path.basename(_file)
            name = self._get_dict_name(_file)
            outputs[name] = os.path.abspath(basename)
        return outputs

    def resample_images_for_features(self, feature_files, ref_file, transform):
        resampled_feature_files = dict()
        for _file in feature_files:
            name = self._get_dict_name(_file)
            resampled_feature_files[name] = run_resample(_file, ref_file, transform,
                                                         self._list_resampled_feature_files()[name], "Linear", "float",
                                                         inverse_transform=self.inputs.inverse_transform)
        return resampled_feature_files


class PredictEdgeProbabilityInputSpec(BaseInterfaceInputSpec):
    t1_file = traits.File(exists=True)
    additional_files = traits.File(exists=True)
    classifier_file = traits.File(exists=True, desc="Classifier file for predicting edge probability")
    out_file = traits.File(exist=False)


class PredictEdgeProbabilityOutputSpec(TraitedSpec):
    out_file = traits.File()


class PredictEdgeProbability(BaseInterface):
    input_spec = PredictEdgeProbabilityInputSpec

    def _run_interface(self, runtime):
        feature_data = image_data(self.inputs.t1_file, "T1", additional_images=self.inputs.additional_files)
        classifier = joblib.load(self.inputs.classifier_file)
        probability_array = classifier.predict_proba(feature_data.values)
        probability_image = image_file_from_array_with_reference_image_file(probability_array, self.inputs.t1_file,
                                                                            self._list_outputs()["out_file"])
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        return outputs

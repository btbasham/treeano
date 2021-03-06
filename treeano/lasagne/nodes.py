import toolz
import numpy as np
import lasagne

from .. import utils
from .. import core
from .. import nodes

# ############################ utils for wrapping ############################


def wrap_lasagne_node(network, in_vw, param_kwargs, constructor, kwargs):
    """
    param_kwargs:
    dict from param name to map of keyword arguments for constructing
    (eg. inits, tags, etc.)
    """
    l_in = lasagne.layers.InputLayer(
        input_var=in_vw.variable,
        shape=in_vw.shape)
    l_out = constructor(l_in, **kwargs)
    output = lasagne.layers.get_output(l_out)
    output_shape = lasagne.layers.get_output_shape(l_out)
    params = lasagne.layers.get_all_params(l_out)
    to_replace = {}
    for param in params:
        name = param.name
        assert name in param_kwargs
        assert "tags" in param_kwargs[name]
        assert "inits" in param_kwargs[name]
        vw = network.create_variable(
            name=name,
            is_shared=True,
            shape=param.get_value().shape,
            **param_kwargs[name]
        )
        to_replace[param] = vw.variable
    new_output, = utils.deep_clone([output], to_replace)
    network.create_variable(
        name="default",
        variable=new_output,
        shape=output_shape,
        tags={"output"},
    )


class LasagneUpdatesNode(nodes.StandardUpdatesNode):

    """
    node that wraps lasagne update functions
    """

    hyperparameter_names = ("cost_reference",
                            "reference",
                            "sgd_learning_rate",
                            "learning_rate")

    def _new_update_deltas(self, network, parameters, grads):
        parameter_variables = [p.variable for p in parameters]
        updates = self._lasagne_updates(network, parameter_variables, grads)
        return core.UpdateDeltas.from_updates(updates)

    def _lasagne_updates(self, network, parameter_variables, grads):
        raise NotImplementedError

# ################################## nodes ##################################


@core.register_node("lasagne_dense")
class DenseNode(core.NodeImpl):

    """
    node wrapping lasagne's DenseLayer
    """

    hyperparameter_names = ("inits",
                            "dense_num_units",
                            "num_units")

    def compute_output(self, network, in_vw):
        inits = list(toolz.concat(network.find_hyperparameters(
            ["inits"],
            [])))
        num_units = network.find_hyperparameter(["dense_num_units",
                                                 "num_units"])
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs=dict(
                W=dict(tags={"parameter", "weight"},
                       inits=inits),
                b=dict(tags={"parameter", "bias"},
                       inits=inits)
            ),
            constructor=lasagne.layers.DenseLayer,
            kwargs=dict(
                num_units=num_units,
                nonlinearity=lasagne.nonlinearities.identity,
            )
        )


def ReLUNode(name):
    return nodes.ApplyNode(name,
                           fn=lasagne.nonlinearities.rectify,
                           shape_fn=utils.identity)

# ################################# updates #################################


@core.register_node("lasagne_sgd")
class SGDNode(LasagneUpdatesNode):

    """
    node that provides updates via SGD
    """

    hyperparameter_names = ("sgd_learning_rate",
                            "learning_rate")

    def _lasagne_updates(self, network, parameter_variables, grads):
        learning_rate = network.find_hyperparameter(["sgd_learning_rate",
                                                     "learning_rate"])
        return lasagne.updates.sgd(grads,
                                   parameter_variables,
                                   learning_rate=learning_rate)


@core.register_node("lasagne_nesterov_momentum")
class NesterovMomentumNode(LasagneUpdatesNode):

    """
    node that provides updates via SGD
    """

    hyperparameter_names = ("learning_rate",
                            "momentum")

    def _lasagne_updates(self, network, parameter_variables, grads):
        learning_rate = network.find_hyperparameter(["learning_rate"])
        momentum = network.find_hyperparameter(["momentum"], 0.9)
        return lasagne.updates.nesterov_momentum(grads,
                                                 parameter_variables,
                                                 learning_rate=learning_rate,
                                                 momentum=momentum)

# ############################### convolutions ###############################


@core.register_node("lasagne_conv2d")
class Conv2DNode(core.NodeImpl):

    """
    node wrapping lasagne's Conv2DLayer
    """

    hyperparameter_names = ("inits",
                            "num_filters",
                            "filter_size",
                            "conv_stride",
                            "stride",
                            "border_mode",
                            "untie_biases")

    def compute_output(self, network, in_vw):
        inits = list(toolz.concat(network.find_hyperparameters(
            ["inits"],
            [])))
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs=dict(
                W=dict(tags={"parameter", "weight"},
                       inits=inits),
                b=dict(tags={"parameter", "bias"},
                       inits=inits)
            ),
            constructor=lasagne.layers.Conv2DLayer,
            kwargs=dict(
                num_filters=network.find_hyperparameter(["num_filters"]),
                filter_size=network.find_hyperparameter(["filter_size"]),
                stride=network.find_hyperparameter(["conv_stride",
                                                    "stride"],
                                                   (1, 1)),
                border_mode=network.find_hyperparameter(["border_mode"],
                                                        "valid"),
                untie_biases=network.find_hyperparameter(["untie_biases"],
                                                         False),
                nonlinearity=lasagne.nonlinearities.identity,
            )
        )


@core.register_node("lasagne_conv2d_dnn")
class Conv2DDNNNode(core.NodeImpl):

    """
    node wrapping lasagne's Conv2DDNNLayer
    """

    hyperparameter_names = ("inits",
                            "num_filters",
                            "filter_size",
                            "conv_stride",
                            "stride",
                            "border_mode",
                            "untie_biases",
                            "flip_filters",)

    def compute_output(self, network, in_vw):
        import lasagne.layers.dnn
        inits = list(toolz.concat(network.find_hyperparameters(
            ["inits"],
            [])))
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs=dict(
                W=dict(tags={"parameter", "weight"},
                       inits=inits),
                b=dict(tags={"parameter", "bias"},
                       inits=inits)
            ),
            constructor=lasagne.layers.dnn.Conv2DDNNLayer,
            kwargs=dict(
                num_filters=network.find_hyperparameter(["num_filters"]),
                filter_size=network.find_hyperparameter(["filter_size"]),
                stride=network.find_hyperparameter(["conv_stride",
                                                    "stride"],
                                                   (1, 1)),
                border_mode=network.find_hyperparameter(["border_mode"],
                                                        "valid"),
                untie_biases=network.find_hyperparameter(["untie_biases"],
                                                         False),
                flip_filters=network.find_hyperparameter(["flip_filters"],
                                                         False),
                nonlinearity=lasagne.nonlinearities.identity,
            )
        )


# ############################### downsampling ###############################


@core.register_node("lasagne_maxpool2d")
class MaxPool2DNode(core.NodeImpl):

    """
    node wrapping lasagne's MaxPool2DLayer
    """

    hyperparameter_names = ("pool_size",
                            "pool_stride",
                            "stride",
                            "pad",
                            "ignore_border")

    def compute_output(self, network, in_vw):
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs={},
            constructor=lasagne.layers.MaxPool2DLayer,
            kwargs=dict(
                pool_size=network.find_hyperparameter(["pool_size"]),
                stride=network.find_hyperparameter(["pool_stride",
                                                    "stride"],
                                                   None),
                pad=network.find_hyperparameter(["pad"], (0, 0)),
                ignore_border=network.find_hyperparameter(["ignore_border"],
                                                          False),
            )
        )


@core.register_node("lasagne_maxpool2d_dnn")
class MaxPool2DDNNNode(core.NodeImpl):

    """
    node wrapping lasagne's MaxPool2DDNNLayer
    """

    hyperparameter_names = ("pool_size",
                            "pool_stride",
                            "stride",
                            "pad")

    def compute_output(self, network, in_vw):
        import lasagne.layers.dnn
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs={},
            constructor=lasagne.layers.dnn.MaxPool2DDNNLayer,
            kwargs=dict(
                pool_size=network.find_hyperparameter(["pool_size"]),
                stride=network.find_hyperparameter(["pool_stride",
                                                    "stride"],
                                                   None),
                pad=network.find_hyperparameter(["pad"], (0, 0)),
            )
        )


@core.register_node("lasagne_meanpool2d_dnn")
class MeanPool2DDNNNode(core.NodeImpl):

    """
    node wrapping lasagne's Pool2DDNNLayer with mode = average_exc_pad
    """

    hyperparameter_names = ("pool_size",
                            "pool_stride",
                            "stride",
                            "pad")

    def compute_output(self, network, in_vw):
        import lasagne.layers.dnn
        wrap_lasagne_node(
            network=network,
            in_vw=in_vw,
            param_kwargs={},
            constructor=lasagne.layers.dnn.Pool2DDNNLayer,
            kwargs=dict(
                # TODO look into which is better
                # can also be mode="average_inc_pad",
                mode="average_exc_pad",
                pool_size=network.find_hyperparameter(["pool_size"]),
                stride=network.find_hyperparameter(["pool_stride",
                                                    "stride"],
                                                   None),
                pad=network.find_hyperparameter(["pad"], (0, 0)),
            )
        )

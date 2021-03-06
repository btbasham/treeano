import nose.tools as nt
import numpy as np
import theano
import theano.tensor as T
import treeano
import treeano.nodes as tn

import canopy

fX = theano.config.floatX


def test_to_shared_dict():
    network = tn.SequentialNode(
        "seq",
        [tn.InputNode("i", shape=(10,)),
         tn.LinearMappingNode(
             "lm",
             output_dim=15,
             inits=[treeano.inits.ConstantInit(42.42)])]
    ).network()
    sd = canopy.network_utils.to_shared_dict(network)
    nt.assert_equal(sd.keys(), ["lm:weight"])
    np.testing.assert_equal(sd.values()[0].get_value(),
                            42.42 * np.ones((10, 15), dtype=fX))


def test_to_value_dict():
    network = tn.SequentialNode(
        "seq",
        [tn.InputNode("i", shape=(10,)),
         tn.LinearMappingNode(
             "lm",
             output_dim=15,
             inits=[treeano.inits.ConstantInit(42.42)])]
    ).network()
    sd = canopy.network_utils.to_value_dict(network)
    nt.assert_equal(sd.keys(), ["lm:weight"])
    np.testing.assert_equal(sd["lm:weight"],
                            42.42 * np.ones((10, 15), dtype=fX))


def test_load_value_dict():
    def new_network():
        return tn.SequentialNode(
            "seq",
            [tn.InputNode("i", shape=(10, 100)),
             tn.LinearMappingNode(
                 "lm",
                 output_dim=15,
                 inits=[treeano.inits.NormalWeightInit()])]
        ).network()

    n1 = new_network()
    n2 = new_network()

    fn1 = n1.function(["i"], ["lm"])
    fn2 = n2.function(["i"], ["lm"])

    x = np.random.randn(10, 100).astype(fX)

    def test():
        np.testing.assert_equal(fn1(x), fn2(x))

    # should fail
    nt.raises(AssertionError)(test)()
    # change weights
    canopy.network_utils.load_value_dict(
        n1, canopy.network_utils.to_value_dict(n2))
    # should not fail
    test()


def test_to_preallocated_init1():
    network1 = tn.SequentialNode(
        "seq",
        [tn.InputNode("i", shape=(3, 4, 5)),
         tn.LinearMappingNode(
             "lm",
             output_dim=15,
             inits=[treeano.inits.NormalWeightInit(15.0)])]
    ).network()
    inits = [canopy.network_utils.to_preallocated_init(network1)]
    network2 = tn.SequentialNode(
        "seq",
        [tn.InputNode("i", shape=(3, 4, 5)),
         tn.LinearMappingNode(
             "lm",
             output_dim=15,
             inits=inits)]
    ).network()

    w1 = canopy.network_utils.to_shared_dict(network1).values()[0]
    w2 = canopy.network_utils.to_shared_dict(network2).values()[0]
    # both networks should be using the exact same shared variables
    assert w1 is w2

    fn1 = network1.function(["i"], ["lm"])
    fn2 = network2.function(["i"], ["lm"])
    x = np.random.randn(3, 4, 5).astype(fX)
    np.testing.assert_equal(fn1(x),
                            fn2(x))


def test_to_preallocated_init2():
    # test that networks are kept in sync even when updating
    network1 = tn.toy.ConstantUpdaterNode(
        "cun",
        tn.SequentialNode(
            "seq",
            [tn.InputNode("i", shape=(3, 4, 5)),
             tn.LinearMappingNode(
                 "lm",
                 output_dim=15,
                 inits=[treeano.inits.NormalWeightInit(15.0)])]),
        value=-0.1,
    ).network()
    inits = [canopy.network_utils.to_preallocated_init(network1)]
    network2 = tn.toy.ConstantUpdaterNode(
        "cun",
        tn.SequentialNode(
            "seq",
            [tn.InputNode("i", shape=(3, 4, 5)),
             tn.LinearMappingNode(
                 "lm",
                 output_dim=15,
                 inits=inits)]),
        value=0.4,
    ).network()

    fn1 = network1.function(["i"], ["lm"])
    fn2 = network2.function(["i"], ["lm"])
    fn1u = network1.function(["i"], ["lm"], include_updates=True)
    fn2u = network2.function(["i"], ["lm"], include_updates=True)
    x = np.random.randn(3, 4, 5).astype(fX)
    np.testing.assert_equal(fn1(x), fn2(x))
    fn1u(x)
    np.testing.assert_equal(fn1(x), fn2(x))
    fn2u(x)
    np.testing.assert_equal(fn1(x), fn2(x))

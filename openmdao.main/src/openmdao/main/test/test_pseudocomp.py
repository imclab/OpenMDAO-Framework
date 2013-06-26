
import unittest

import ast

from openmdao.main.api import Assembly, Component, set_as_top
from openmdao.main.datatypes.api import Float, Array
from openmdao.main.pseudocomp import unit_transform
from openmdao.units.units import PhysicalQuantity
from openmdao.main.printexpr import print_node

class Simple(Component):
    a = Float(iotype='in', units='inch')
    b = Float(iotype='in', units='inch')
    c = Float(iotype='out', units='ft')
    d = Float(iotype='out', units='ft')
    dist = Float(iotype='out', units='ft')
    time = Float(iotype='out', units='s')
    speed = Float(iotype='in', units='inch/s')
    arr = Array([1.,2.,3.], iotype='out', units='ft')
    
    def __init__(self):
        super(Simple, self).__init__()
        self.a = 1
        self.b = 2
        self.c = 3
        self.d = -1

    def execute(self):
        self.c = PhysicalQuantity(self.a + self.b, 'inch').in_units_of('ft').value
        self.d = PhysicalQuantity(self.a - self.b, 'inch').in_units_of('ft').value

class SimpleNoUnits(Component):
    a = Float(iotype='in')
    b = Float(iotype='in')
    c = Float(iotype='out')
    d = Float(iotype='out')
    arr = Array([1.,2.,3.], iotype='out')
    
    def __init__(self):
        super(SimpleNoUnits, self).__init__()
        self.a = 1
        self.b = 2
        self.c = 3
        self.d = -1

    def execute(self):
        self.c = self.a + self.b
        self.d = self.a - self.b
        

def _simple_model(units=True):
    if units:
        klass = Simple
    else:
        klass = SimpleNoUnits
    top = set_as_top(Assembly())
    top.add("comp1", klass())
    top.add("comp2", klass())
    top.driver.workflow.add(['comp1','comp2'])
    top.connect("comp1.c", "comp2.a")
    return top

class PseudoCompTestCase(unittest.TestCase):

    def setUp(self):
        self.fakes = ['@bin','@bout','@xin','@xout']

    def test_basic_nounits(self):
        top = _simple_model(units=False)
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2','driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('comp1.c', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper.list_connections(visible_only=True)),
                         set([('comp1.c', 'comp2.a')]))

    def test_basic_units(self):
        top = _simple_model()
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2','_0','driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), 
                              ('comp1.c', '_0.in0')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('_0.out0', 'comp2.a'), 
                              ('comp1.c', '_0.in0'),
                              ('comp1.c', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper.list_connections(visible_only=True)),
                         set([('comp1.c', 'comp2.a')]))
        self.assertEqual(top._0._eqn, 'out0 = in0*12.0')
        top.comp1.a = 12.
        top.comp1.b = 24.
        top.run()
        self.assertAlmostEqual(top.comp1.c, 3.)
        self.assertAlmostEqual(top.comp2.a, 36.)
        
    def test_multi_src(self):
        top = _simple_model()  # comp1.c --> comp2.a
        top.connect('comp1.dist/comp1.time', 'comp2.speed')
        top.comp1.dist = 10.
        top.comp1.time = 5.
        # dist/time = 2 ft/sec
        top.run()
        self.assertAlmostEqual(top.comp2.speed, 24.) # speed = 24 inch/s

        self.assertTrue(hasattr(top, '_0'))
        self.assertTrue(hasattr(top, '_1'))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0', '_1']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.time', 'comp2.speed'),
                              ('comp1.dist', 'comp2.speed'),
                              ('comp1.c', 'comp2.a')]))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', 
                              '_0', '_1', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0'),
                              ('comp1.dist', '_1.in1'), ('comp1.time', '_1.in0'),
                              ('_1.out0', 'comp2.speed')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), 
                              ('_1.out0', 'comp2.speed'), ('comp1.dist', '_1.in1'), 
                              ('comp1.dist/comp1.time', 'comp2.speed'), 
                              ('_0.out0', 'comp2.a'), ('comp1.time', '_1.in0')]))
        
        # disconnect two linked expressions
        top.disconnect('comp1.dist/comp1.time')
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'),
                              ('_0.out0', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper._exprgraph.nodes()),
                         set(['comp1.c', 'comp2.a', '_0.out0', '_0.in0']))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', '_0', 'driver']+self.fakes))
        self.assertFalse(hasattr(top, '_1'))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.c', 'comp2.a')]))
        
        top.run()
        top.connect('comp1.dist/comp1.time', 'comp2.speed')
        self.assertTrue(hasattr(top, '_2'))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', '_0', '_2', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0'),
                              ('comp1.dist', '_2.in1'), ('comp1.time', '_2.in0'),
                              ('_2.out0', 'comp2.speed')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), 
                              ('_2.out0', 'comp2.speed'), ('comp1.dist', '_2.in1'), 
                              ('comp1.dist/comp1.time', 'comp2.speed'), 
                              ('_0.out0', 'comp2.a'), ('comp1.time', '_2.in0')]))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0', '_2']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.time', 'comp2.speed'),
                              ('comp1.dist', 'comp2.speed'),
                              ('comp1.c', 'comp2.a')]))
        
        # disconnect a single variable
        top.disconnect('comp1.dist')
        self.assertFalse(hasattr(top, '_2'))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', 
                              '_0', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), ('_0.out0', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.c', 'comp2.a')]))

        top.run()
        top.connect('comp1.dist/comp1.time', 'comp2.speed')
        self.assertTrue(hasattr(top, '_3'))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', '_0', '_3', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0'),
                              ('comp1.dist', '_3.in1'), ('comp1.time', '_3.in0'),
                              ('_3.out0', 'comp2.speed')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), 
                              ('_3.out0', 'comp2.speed'), ('comp1.dist', '_3.in1'), 
                              ('comp1.dist/comp1.time', 'comp2.speed'), 
                              ('_0.out0', 'comp2.a'), ('comp1.time', '_3.in0')]))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0', '_3']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.time', 'comp2.speed'),
                              ('comp1.dist', 'comp2.speed'),
                              ('comp1.c', 'comp2.a')]))
        
        # disconnect a whole component
        top.disconnect('comp2')
        self.assertFalse(hasattr(top, '_3'))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([]))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set())
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set())

    def test_multi_src_arr(self):
        top = _simple_model()  # comp1.c --> comp2.a
        top.connect('comp1.arr[1]/comp1.time', 'comp2.speed')
        top.comp1.arr[1] = 10.
        top.comp1.time = 5.
        # arr[1]/time = 2 ft/sec
        top.run()
        self.assertAlmostEqual(top.comp2.speed, 24.) # speed = 24 inch/s

        self.assertTrue(hasattr(top, '_0'))
        self.assertTrue(hasattr(top, '_1'))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0', '_1']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.time', 'comp2.speed'),
                              ('comp1.arr[1]', 'comp2.speed'),
                              ('comp1.c', 'comp2.a')]))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', 
                              '_0', '_1', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0'),
                              ('comp1.arr[1]', '_1.in1'), ('comp1.time', '_1.in0'),
                              ('_1.out0', 'comp2.speed')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), 
                              ('_1.out0', 'comp2.speed'), ('comp1.arr[1]', '_1.in1'), 
                              ('comp1.arr[1]/comp1.time', 'comp2.speed'), 
                              ('_0.out0', 'comp2.a'), ('comp1.time', '_1.in0')]))
        
        # disconnect a single variable
        top.disconnect('comp1.arr[1]')
        self.assertFalse(hasattr(top, '_2'))
        self.assertEqual(set(top._depgraph._graph.nodes()),
                         set(['comp1','comp2', 
                              '_0', 'driver']+self.fakes))
        self.assertEqual(set(top._depgraph.list_connections()),
                         set([('_0.out0', 'comp2.a'), ('comp1.c', '_0.in0')]))
        self.assertEqual(set(top._exprmapper.list_connections()),
                         set([('comp1.c', 'comp2.a'), ('comp1.c', '_0.in0'), ('_0.out0', 'comp2.a')]))
        self.assertEqual(set(top._exprmapper.list_pseudocomps()),
                         set(['_0']))
        self.assertEqual(set(top.list_connections(visible_only=True)),
                         set([('comp1.c', 'comp2.a')]))

    def test_multi_src_boundary_var(self):
        top = _simple_model()  # comp1.c --> comp2.a
        top.add('arr', Array([1.,2.,3.,4.], iotype='in', units='ft'))
        top.add('spd_out', Float(0., iotype='out', units='inch/s'))
        
        top.connect('arr[1]/comp1.time', 'spd_out')
        top.arr[1] = 10.
        top.comp1.time = 5.
        # arr[1]/time = 2 ft/sec
        top.run()
        self.assertAlmostEqual(top.spd_out, 24.) # spd_out = 24 inch/s
        

    # disconnect() for a boundary var in an expr  
       

class UnitXformerTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_conversion(self):
        node = ast.parse('a')
        cnv = unit_transform(node, 'ft', 'inch')
        newexpr = print_node(cnv)
        self.assertEqual(newexpr, 'a*12.0')

    def test_scaler_adder_conversion(self):
        node = ast.parse('a')
        cnv = unit_transform(node, 'degC', 'degF')
        newexpr = print_node(cnv)
        self.assertEqual(newexpr, 'a*1.8+32.0')
        


if __name__ == '__main__':
    unittest.main()

    

import unittest
from worlds import *
class Rules(unittest.TestCase):
    def world(self,rules):return World('unit',0,[{'x':0,'y':0,'size':1,'color':'red'},{'x':4,'y':0,'size':1,'color':'blue'}],1,rules)
    def test_simultaneous_rhs_and_last_write(self):
        w=self.world([{'event':1,'when':['const',1],'assign':[[0,['bit',1]],[1,['bit',0]]]}])
        self.assertEqual(step(w,1,1),2)
        w.rules.append({'event':1,'when':['bit',0],'assign':[[1,['const',0]]]})
        self.assertEqual(step(w,1,1),0)
    def test_disabled_rule(self):
        w=self.world([{'event':-1,'when':['bit',0],'assign':[[1,['const',1]]]}])
        self.assertEqual(step(w,1,0),3);self.assertEqual(step(w,1,0,(0,)),1)
    def test_offsite_click_not_noop(self):
        w=self.world([{'event':0,'when':['const',1],'assign':[[0,['const',0]]]}])
        a=abstract(w,{'type':'click','x':15,'y':15});self.assertEqual(step(w,1,a),1);self.assertEqual(step(w,1,0),0)
    def test_observation_decode(self):
        w=generate(812)
        for s in range(1<<w.n):self.assertEqual(decode_observation(w,render(w,s)),s)
    def test_vector_scalar_exhaustive(self):
        for seed in range(801,806):
            w=generate(seed);table=transition_table(w)
            for s in range(1<<w.n):
                for a in range(w.action_count):self.assertEqual(int(table[s,a]),step(w,s,a))
if __name__=='__main__':unittest.main()

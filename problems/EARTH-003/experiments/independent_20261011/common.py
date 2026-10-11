"""Standard-library semantic comparator; hashes are separate integrity checks."""
import math

def compare(expected, observed, tolerance, path='root'):
    errors=[]; gaps=[]
    def visit(a,b,p):
        if isinstance(a,dict):
            if not isinstance(b,dict) or set(a)!=set(b):
                errors.append({'path':p,'reason':'key/domain mismatch'});return
            for k in a:visit(a[k],b[k],p+'.'+str(k))
        elif isinstance(a,list):
            if not isinstance(b,list) or len(a)!=len(b):
                errors.append({'path':p,'reason':'length mismatch'});return
            for i,(x,y) in enumerate(zip(a,b)):visit(x,y,p+'.'+str(i))
        elif type(a) is int:
            if type(b) is not int or a!=b:errors.append({'path':p,'reason':'integer mismatch','expected':a,'observed':b})
        elif isinstance(a,float):
            if not math.isfinite(a):
                errors.append({'path':p,'reason':'nonfinite reference'});return
            if type(b) not in (int,float) or not math.isfinite(b):
                errors.append({'path':p,'reason':'nonfinite/not numeric'});return
            gap=abs(a-b);gaps.append(gap)
            if gap>tolerance:errors.append({'path':p,'reason':'numeric mismatch','gap':gap,'expected':a,'observed':b})
        elif a!=b:errors.append({'path':p,'reason':'value mismatch','expected':a,'observed':b})
    visit(expected,observed,path)
    return {'accepted':not errors,'errors':errors,'max_numeric_gap':max(gaps,default=0.0)}

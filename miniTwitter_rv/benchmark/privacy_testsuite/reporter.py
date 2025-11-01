from datetime import datetime
import os.path, os

import pandas as pd
from pandas.api.types import is_numeric_dtype
import matplotlib.pyplot as plt
from tqdm import tqdm

plt.rcParams.update({'text.usetex': True,
                     'font.family': 'serif',
                     'font.serif': 'Times',
                     'font.size': 15,
                     'savefig.dpi': 300})

COLORS = ["orange", "b", "r"]

class Reporter:

    def __init__(self, title, data, dep_vars=None, indep_vars=None, nu=True):
        self.title = title
        if type(data) is str:
            self.folder = data
            self.data = pd.read_csv(os.path.join(self.folder, "report.csv"), header=0).fillna(0)
            vars_ = list(self.data.columns)
            #print(self.data)
            if type(dep_vars) is int:
                self.dep_vars = vars_[-dep_vars:]
                self.indep_vars = vars_[:-dep_vars]
            else:
                self.dep_vars = [v for v in vars_ if v[0] == "t" and v != "t"]
                self.indep_vars = [v for v in vars_ if v[0] != "t"]
            if len(self.dep_vars) == 0:
                self.dep_vars = ["t"]
        else:
            self.data = pd.DataFrame(data)
            self.dep_vars = dep_vars
            self.indep_vars = indep_vars
            self.folder = None

    def dep_var_name(self, v):
        if v == "t_consent":
            return "consent"
        elif v == "t_monitor":
            return "verdict"
        elif v == "t_other":
            return "computation"

    def _folder(self, root_folder):
        if self.folder is None:
            folder = os.path.join(root_folder, self.title + "_" + str(datetime.now()))
            if not os.path.exists(folder):
                os.mkdir(folder)
            self.folder = folder
            return folder
        else:
            return self.folder

    def save(self, root_folder):
        self.data.to_csv(os.path.join(self._folder(root_folder), "report.csv"), index=False)

    def build_graph(self, title, xlabel, ylabels, x, y, baseline_y):
        fig, ax = plt.subplots(figsize=(2,1.5))
        #fig.suptitle(title.replace("_", "\_"))
        #ax.set_xlabel(xlabel)
        ax.set_xscale('log')
        #ax.set_ylabel('Time (s)')
        #print(y)
        #ax.set_ylim(0, max(y)*1.1)
        #print(x, y)
        #print(x, [y[col] for col in y.columns[::-1]],map(self.dep_var_name, ylabels[::-1]))
        ax.stackplot(x[:y.shape[0]], [y[col] for col in y.columns[::-1]], labels=map(self.dep_var_name, ylabels[::-1]), colors=COLORS)
        tot = None
        for col in y.columns[::-1]:
            if tot is None:
                tot = y[col].copy()
            else:
                tot += y[col]
            ax.plot(x[:y.shape[0]], tot, color='black')#, marker='o')
        if baseline_y is not None and baseline_y.shape[0]:
            ax.plot(x, baseline_y, color='black', linestyle='dashed',
                    marker='s', label='Python/Flask')
        df = pd.DataFrame()
        df[self.dep_vars] = (y*1000)#.astype(int)
        if baseline_y is not None:
            df["Latency (baseline)"] = (baseline_y*1000).astype(int)
            df["Overhead"] = (df[self.dep_vars[0]] / df["Latency (baseline)"]).apply(lambda x: "{:.1f}".format(x))
        df.index = x[:y.shape[0]]
        print(title)
        print(df)
        fig.tight_layout()
        return fig
    
    def generate(self, root_folder, create_folder=True, baseline_folder=None, **kwargs):
        self.folder = self._folder(root_folder)
        if baseline_folder:
            baseline_data = pd.read_csv(os.path.join(baseline_folder, "report.csv"), header=0).fillna(0)
        for indep_var in tqdm(self.indep_vars):
            other_indep_vars = [v for v in self.indep_vars if v != indep_var]
            for vals, gdf in self.data.groupby(other_indep_vars):

                vals = vals if type(vals) is tuple else [vals]
                vals_str = ", ".join([f"{a} = {b}" for (a, b) in list(zip(other_indep_vars, vals)) + list(kwargs.items())])
                gdf2 = gdf.groupby(indep_var)[[var for var in self.dep_vars if var in gdf.columns]].mean().reset_index()

                if baseline_folder:
                    other_indep_vars2 = [var for var in other_indep_vars
                                         if var in baseline_data.columns]
                    vals2 = [val for (i, val) in enumerate(vals)
                             if other_indep_vars[i] in baseline_data.columns]
                    bs = baseline_data[(baseline_data[other_indep_vars2] == vals2).all(axis=1)]
                    if indep_var not in bs.columns:
                        x = list(gdf[indep_var])
                    else:
                        x = sorted(list(set(gdf2[indep_var]) | set(bs[indep_var])))
                    if indep_var not in bs.columns:
                        bs = None
                    else:
                        bs = bs.groupby(indep_var)['t'].mean().reset_index()
                        try:
                            bs = bs['t']
                        except:
                            bs = None
                else:
                    bs = None
                    x = list(gdf2[indep_var])
                if gdf2.shape[0] > 1 and is_numeric_dtype(gdf2[indep_var]):
                    #if indep_var == 'n' and 'u' in other_indep_vars:
                        #fac = pd.Series(vals, index=other_indep_vars)['u']
                        #gdf2['n'] *= fac
                        #x = [i*fac for i in x]
                        #print(gdf2)
                    fig = self.build_graph(vals_str, indep_var, self.dep_vars,
                                           x, gdf2[self.dep_vars], bs)
                    fig.savefig(os.path.join(self.folder, vals_str + ".png"),
                                bbox_inches='tight', pad_inches=0)
                    plt.close()
                elif gdf2.shape[0] > 1:
                    df = pd.DataFrame()
                    df[self.dep_vars] = gdf2[self.dep_vars]*1000
                    if bs is not None:
                        df["Latency (baseline)"] = bs*1000
                        df["Overhead"] = (df[self.dep_vars[0]] / df["Latency (baseline)"]).apply(lambda x: "{:.1f}".format(x))
                        df["Latency (baseline)"] = df["Latency (baseline)"]#.astype(int)
                    #df[self.dep_vars] = df[self.dep_vars].astype(int)
                    df.index = list(gdf2[indep_var])
                    print(vals_str)
                    print(df)

                    
            
                

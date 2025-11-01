import os.path

from tqdm import tqdm

class Tester:

    DEFAULT_N = 20
    
    def __init__(self, title, App, Reporter, root_folder, policy):
        self.App = App
        self.Reporter = Reporter
        self.title = title
        self.root_folder = root_folder
        self.reporter = None
        self.policy = policy
        
    def test(self, N=DEFAULT_N, folder=None):
        data = []
        app = self.App()
        app.start(self.policy)
        configs = app.configurations()
        scenarios = app.scenarios(self.policy)
        cs = [(config, scenario) for config in configs for scenario in scenarios]
        for (config, scenario) in tqdm(cs):
            scenario.initialize(config)
            for _ in range(N):
                result = scenario.run()
                if isinstance(result, dict) and all(key in result for key in ['sc', 'u', 'n', 't']):
                    data.append(result)
                else:
                    print(f"Invalid result for scenario {scenario.sc} with config {config}: {result}")
                scenario.continue_()
            scenario.finalize()
        app.stop()
        self.reporter = self.Reporter(self.title, data, app.dep_vars(), app.indep_vars())
        if folder is not None:
            self.reporter.save(folder)
        self.N = N

    def load(self, N=DEFAULT_N):
        self.reporter = self.Reporter(self.title, data=os.path.join(self.root_folder))
        self.N = N
            
    def generate(self, baseline=None):
        assert(self.reporter is not None)
        self.reporter.generate(self.root_folder, N=self.N, baseline_folder=baseline)


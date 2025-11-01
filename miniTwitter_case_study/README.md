# WhyEnf case study
This repository contains the instrumentation library used to evaluate the enforcer WhyEnf. 
### Setup
1. download the WhyEnf enforcer from the following repository: https://github.com/runtime-enforcement/whyenf.git 
2. specify the handlers and the mappings that invoke the handlers in the application
3. import mappings of handlers to the file ```runThreads.py``` 
4. instrument the models and urlpatterns by specifying which actions you want to intercept 
5. specify the enforcer, formula and signature when running ```manage.py```

example run:
```
manage.py runserver --noreload -exe=whyenf/bin/whyenf.exe -sig=examples/example_sig.sig -formula=examples/consent.mfotl
```
### Data 
The data of the paper can be found in the folders [logs](https://gitlab.inf.ethz.ch/skrstic/proactive-enforcement-library/-/tree/main/miniTwitter_case_study/logs?ref_type=heads) and [plots](https://gitlab.inf.ethz.ch/skrstic/proactive-enforcement-library/-/tree/main/miniTwitter_case_study/plots?ref_type=heads)

### Benchmark 
An example to run the [benchmark](https://gitlab.inf.ethz.ch/skrstic/proactive-enforcement-library/-/tree/main/miniTwitter_case_study/benchmark/privacy_testsuite?ref_type=heads)
```
/benchmark/privacy_testsuite/privacy_test.py "baseline_mytwitt-django", "-f", "output",  "-sig", "examples/example_sig.sig", "-formula", "examples/deletion.mfotl", "-exe", "whyenf/bin/whyenf.exe"
```






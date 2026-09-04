# Introduction
This repository contains the instrumentation library used to specify
a policy enforcement point (PEP) for Python web applications.
It is tailored for batched policy decision points (PDPs), like EnfGuard.

# Structure


The repository is structured as follows:

- `instrlib/`: Contains the instrumentation library code
- `tests/`: Contains unit tests for the library
- `*_case_study/`: Contains case studies showcasing the use of the library
GDPRFS case study: **Please find the GDPRFS README [here](gdprfs/README.md).**

# General Usage
1. Download the WhyEnf enforcer from the following repository: https://github.com/runtime-enforcement/enfguard.git 
2. Specify the handlers and the mappings that invoke the handlers in the application
3. Import the mappings of handlers to the file ```runThreads.py``` 
4. Instrument the models and urlpatterns by specifying which actions you want to intercept 
5. Specify the enforcer, formula and signature when running ```manage.py```


# Case Studies

To run the case studies, see the README files in the respective directories.


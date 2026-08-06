"""Route-aware pharmacokinetic modelling.

The legacy depot model in ``utils/pk_model.py`` remains untouched and continues
to serve the original ``/api/v1/pk/simulate`` endpoint. This package adds the
route awareness, parameter provenance and input-source separation that the depot
model alone could not express.
"""

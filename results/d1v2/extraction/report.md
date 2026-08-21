# Extraction gap test (arrangement features)


## seed 0

- shallow: overall 0.755 [0.663,0.847]  boundary 0.524 [0.332,0.714] (n=21)
- shallow_plus_structural: overall 0.857 [0.786,0.918]  boundary 0.762 [0.571,0.905] (n=21)
- struct_plus_arrangement: overall 0.918 [0.867,0.969]  boundary 0.952 [0.857,1.000] (n=21)
- control_encoder_summary: overall 0.908 [0.837,0.959]  boundary 0.905 [0.762,1.000] (n=21)

## seed 1

- shallow: overall 0.776 [0.684,0.857]  boundary 0.435 [0.217,0.652] (n=23)
- shallow_plus_structural: overall 0.857 [0.786,0.918]  boundary 0.783 [0.609,0.957] (n=23)
- struct_plus_arrangement: overall 0.908 [0.847,0.959]  boundary 0.913 [0.783,1.000] (n=23)
- control_encoder_summary: overall 0.857 [0.786,0.918]  boundary 0.783 [0.609,0.913] (n=23)

## seed 2

- shallow: overall 0.714 [0.622,0.796]  boundary 0.542 [0.333,0.750] (n=24)
- shallow_plus_structural: overall 0.857 [0.786,0.929]  boundary 0.708 [0.500,0.875] (n=24)
- struct_plus_arrangement: overall 0.857 [0.786,0.918]  boundary 0.875 [0.708,1.000] (n=24)
- control_encoder_summary: overall 0.827 [0.745,0.898]  boundary 0.750 [0.583,0.917] (n=24)

## seed 3

- shallow: overall 0.714 [0.622,0.796]  boundary 0.520 [0.320,0.720] (n=25)
- shallow_plus_structural: overall 0.878 [0.806,0.939]  boundary 0.760 [0.600,0.920] (n=25)
- struct_plus_arrangement: overall 0.867 [0.796,0.929]  boundary 0.760 [0.599,0.920] (n=25)
- control_encoder_summary: overall 0.918 [0.857,0.969]  boundary 0.920 [0.800,1.000] (n=25)

## Verdict: CLOSED (3/4 seeds with augmented >= encoder on boundary)

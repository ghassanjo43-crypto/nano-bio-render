"""
Pharmacokinetic/Pharmacodynamic Simulation Module
Two-compartment model implementation
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Tuple

# NumPy compatibility: trapezoid (NumPy 2.0+) vs trapz (NumPy <2.0)
if hasattr(np, 'trapezoid'):
    np_trapz = np.trapezoid
else:
    np_trapz = np.trapz

def two_compartment_model(
    dose: float,
    kabs: float,
    kel: float,
    k12: float,
    k21: float,
    duration: float = 48.0,
    dt: float = 0.1
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate two-compartment pharmacokinetic model
    
    Parameters:
    -----------
    dose : float
        Initial dose (mg/kg)
    kabs : float
        Absorption rate constant (h^-1)
    kel : float
        Elimination rate constant from central compartment (h^-1)
    k12 : float
        Transfer rate constant: central → peripheral (h^-1)
    k21 : float
        Transfer rate constant: peripheral → central (h^-1)
    duration : float
        Simulation time (hours)
    dt : float
        Time step (hours)
    
    Returns:
    --------
    time : ndarray
        Time points
    C_plasma : ndarray
        Plasma/central compartment concentration
    C_tissue : ndarray
        Tissue/peripheral compartment concentration
    """
    
    # Time array
    time = np.arange(0, duration + dt, dt)
    n_points = len(time)
    
    # Initialize compartments
    C_plasma = np.zeros(n_points)
    C_tissue = np.zeros(n_points)
    C_depot = np.zeros(n_points)
    
    # Initial dose in depot
    C_depot[0] = dose
    
    # Euler integration
    for i in range(n_points - 1):
        # Depot compartment (absorption site)
        dC_depot = -kabs * C_depot[i]
        
        # Central compartment (plasma)
        dC_plasma = (
            kabs * C_depot[i]  # Absorption from depot
            - kel * C_plasma[i]  # Elimination
            - k12 * C_plasma[i]  # Transfer to peripheral
            + k21 * C_tissue[i]  # Return from peripheral
        )
        
        # Peripheral compartment (tissue)
        dC_tissue = (
            k12 * C_plasma[i]  # Transfer from central
            - k21 * C_tissue[i]  # Return to central
        )
        
        # Update concentrations
        C_depot[i + 1] = C_depot[i] + dC_depot * dt
        C_plasma[i + 1] = C_plasma[i] + dC_plasma * dt
        C_tissue[i + 1] = C_tissue[i] + dC_tissue * dt
    
    return time, C_plasma, C_tissue

def calculate_pk_parameters(
    time: np.ndarray,
    C_plasma: np.ndarray,
    C_tissue: np.ndarray
) -> Dict[str, float]:
    """
    Calculate key pharmacokinetic parameters
    
    Parameters:
    -----------
    time : ndarray
        Time points
    C_plasma : ndarray
        Plasma concentration-time profile
    C_tissue : ndarray
        Tissue concentration-time profile
    
    Returns:
    --------
    parameters : dict
        Dictionary of PK parameters
    """
    
    # C_max (peak concentration)
    C_max_plasma = np.max(C_plasma)
    C_max_tissue = np.max(C_tissue)
    
    # T_max (time to peak)
    T_max_plasma = time[np.argmax(C_plasma)]
    T_max_tissue = time[np.argmax(C_tissue)]
    
    # AUC (area under curve) - trapezoidal rule
    AUC_plasma = np_trapz(C_plasma, time)
    AUC_tissue = np_trapz(C_tissue, time)
    
    # Half-life (approximate from terminal phase)
    # Find time when concentration drops to 50% of C_max
    idx_max_plasma = np.argmax(C_plasma)
    try:
        idx_half = idx_max_plasma + np.where(C_plasma[idx_max_plasma:] <= C_max_plasma / 2)[0][0]
        t_half_plasma = time[idx_half] - T_max_plasma
    except:
        t_half_plasma = None
    
    # Tissue accumulation ratio
    tissue_accumulation = AUC_tissue / AUC_plasma if AUC_plasma > 0 else 0
    
    # Steady-state volume ratio
    Vss_ratio = C_max_tissue / C_max_plasma if C_max_plasma > 0 else 0
    
    return {
        'C_max_plasma': C_max_plasma,
        'C_max_tissue': C_max_tissue,
        'T_max_plasma': T_max_plasma,
        'T_max_tissue': T_max_tissue,
        'AUC_plasma': AUC_plasma,
        'AUC_tissue': AUC_tissue,
        't_half_plasma': t_half_plasma,
        'tissue_accumulation_ratio': tissue_accumulation,
        'Vss_ratio': Vss_ratio
    }

def simulate_release_profile(
    time: np.ndarray,
    release_type: str = "sustained",
    burst_fraction: float = 0.2,
    release_rate: float = 0.1
) -> np.ndarray:
    """
    Simulate drug release profile from nanoparticle
    
    Parameters:
    -----------
    time : ndarray
        Time points
    release_type : str
        Type of release: 'burst', 'sustained', 'controlled'
    burst_fraction : float
        Fraction released in burst phase (0-1)
    release_rate : float
        Release rate constant (h^-1)
    
    Returns:
    --------
    release : ndarray
        Cumulative fraction released over time
    """
    
    if release_type == "burst":
        # Rapid initial release
        release = burst_fraction + (1 - burst_fraction) * (1 - np.exp(-3 * release_rate * time))
    
    elif release_type == "sustained":
        # Gradual release with initial burst
        release = burst_fraction + (1 - burst_fraction) * (1 - np.exp(-release_rate * time))
    
    elif release_type == "controlled":
        # Zero-order-like release
        release = np.minimum(1.0, release_rate * time / 10)
    
    else:  # default sustained
        release = 1 - np.exp(-release_rate * time)
    
    return release

def create_pk_plot(
    time: np.ndarray,
    C_plasma: np.ndarray,
    C_tissue: np.ndarray,
    pk_params: Dict[str, float],
    design: Dict
) -> plt.Figure:
    """
    Create pharmacokinetic visualization plot
    
    Parameters:
    -----------
    time : ndarray
        Time points
    C_plasma : ndarray
        Plasma concentration
    C_tissue : ndarray
        Tissue concentration
    pk_params : dict
        PK parameters
    design : dict
        Nanoparticle design parameters
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        Generated plot
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Plot 1: Concentration-time profiles
    ax1.plot(time, C_plasma, 'b-', linewidth=2, label='Plasma (Central)')
    ax1.plot(time, C_tissue, 'r-', linewidth=2, label='Tissue (Peripheral)')
    ax1.axhline(y=pk_params['C_max_plasma'], color='b', linestyle='--', alpha=0.5, label=f"C_max plasma: {pk_params['C_max_plasma']:.2f}")
    ax1.axhline(y=pk_params['C_max_tissue'], color='r', linestyle='--', alpha=0.5, label=f"C_max tissue: {pk_params['C_max_tissue']:.2f}")
    
    ax1.set_xlabel('Time (hours)', fontsize=11)
    ax1.set_ylabel('Concentration (arbitrary units)', fontsize=11)
    ax1.set_title(f'Pharmacokinetic Profile: {design.get("Material", "Lipid NP")} ({design.get("Target", "Liver Cells")})', fontsize=12, fontweight='bold')
    ax1.legend(loc='best', framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, time[-1])
    ax1.set_ylim(0, max(np.max(C_plasma), np.max(C_tissue)) * 1.1)
    
    # Plot 2: Release profile
    release = simulate_release_profile(time, release_type="sustained", release_rate=0.1)
    ax2.plot(time, release * 100, 'g-', linewidth=2, label='Cumulative Release')
    ax2.fill_between(time, 0, release * 100, alpha=0.3, color='green')
    
    ax2.set_xlabel('Time (hours)', fontsize=11)
    ax2.set_ylabel('Cumulative Release (%)', fontsize=11)
    ax2.set_title('Drug Release Profile', fontsize=12, fontweight='bold')
    ax2.legend(loc='best', framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, time[-1])
    ax2.set_ylim(0, 105)
    
    plt.tight_layout()
    
    return fig

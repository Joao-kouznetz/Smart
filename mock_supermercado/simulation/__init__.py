"""Ferramentas para simular compras no mock do supermercado."""

from mock_supermercado.simulation.purchase_simulator import (
    SimulationResult,
    distance_between_products,
    populate_simulated_purchases,
)

__all__ = [
    "SimulationResult",
    "distance_between_products",
    "populate_simulated_purchases",
]

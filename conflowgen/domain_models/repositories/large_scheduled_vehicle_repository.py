import logging
from typing import Dict, List, Callable, Type

from conflowgen.domain_models.container import Container
from conflowgen.domain_models.data_types.container_length import ContainerLength
from conflowgen.domain_models.data_types.mode_of_transport import ModeOfTransport
from conflowgen.domain_models.vehicle import LargeScheduledVehicle, AbstractLargeScheduledVehicle


class LargeScheduledVehicleRepository:

    ignored_capacity = ContainerLength.get_factor(ContainerLength.other)

    def __init__(self):
        self.transportation_buffer = None
        self.free_capacity_for_outbound_journey_buffer: Dict[Type[AbstractLargeScheduledVehicle], float] = {}
        self.free_capacity_for_inbound_journey_buffer: Dict[Type[AbstractLargeScheduledVehicle], float] = {}
        self.logger = logging.getLogger("conflowgen")

    def set_transportation_buffer(self, transportation_buffer: float):
        assert -1 < transportation_buffer
        self.transportation_buffer = transportation_buffer

    def reset_cache(self):
        self.free_capacity_for_outbound_journey_buffer = {}
        self.free_capacity_for_inbound_journey_buffer = {}

    @staticmethod
    def load_all_vehicles() -> Dict[ModeOfTransport, List[Type[AbstractLargeScheduledVehicle]]]:
        result = {}
        for vehicle_type in ModeOfTransport.get_scheduled_vehicles():
            large_schedule_vehicle_as_subtype = AbstractLargeScheduledVehicle.map_mode_of_transport_to_class(
                vehicle_type)
            result[vehicle_type] = list(large_schedule_vehicle_as_subtype.select().join(LargeScheduledVehicle))
        return result

    def block_capacity_for_inbound_journey(
            self,
            vehicle: Type[AbstractLargeScheduledVehicle],
            container: Container
    ) -> bool:
        assert vehicle in self.free_capacity_for_inbound_journey_buffer, \
            "First .get_free_capacity_for_inbound_journey(vehicle) must be invoked"

        # calculate new free capacity
        free_capacity_in_teu = self.free_capacity_for_inbound_journey_buffer[vehicle]
        used_capacity_in_teu = ContainerLength.get_factor(container_length=container.length)
        new_free_capacity_in_teu = free_capacity_in_teu - used_capacity_in_teu
        assert new_free_capacity_in_teu >= 0, f"vehicle {vehicle} is overloaded, " \
                                              f"free_capacity_in_teu: {free_capacity_in_teu}, " \
                                              f"used_capacity_in_teu: {used_capacity_in_teu}, " \
                                              f"new_free_capacity_in_teu: {new_free_capacity_in_teu}"

        self.free_capacity_for_inbound_journey_buffer[vehicle] = new_free_capacity_in_teu
        vehicle_capacity_is_exhausted = new_free_capacity_in_teu < self.ignored_capacity
        return vehicle_capacity_is_exhausted

    def block_capacity_for_outbound_journey(
            self,
            vehicle: Type[AbstractLargeScheduledVehicle],
            container: Container
    ) -> bool:
        assert vehicle in self.free_capacity_for_outbound_journey_buffer, \
            "First .get_free_capacity_for_outbound_journey(vehicle) must be invoked"

        # calculate new free capacity
        free_capacity_in_teu = self.free_capacity_for_outbound_journey_buffer[vehicle]
        used_capacity_in_teu = ContainerLength.get_factor(container_length=container.length)
        new_free_capacity_in_teu = free_capacity_in_teu - used_capacity_in_teu
        assert new_free_capacity_in_teu >= 0, f"vehicle {vehicle} is overloaded, " \
                                              f"free_capacity_in_teu: {free_capacity_in_teu}, " \
                                              f"used_capacity_in_teu: {used_capacity_in_teu}, " \
                                              f"new_free_capacity_in_teu: {new_free_capacity_in_teu}"

        self.free_capacity_for_outbound_journey_buffer[vehicle] = new_free_capacity_in_teu
        return new_free_capacity_in_teu <= self.ignored_capacity

    # noinspection PyTypeChecker
    def get_free_capacity_for_inbound_journey(self, vehicle: Type[AbstractLargeScheduledVehicle]) -> float:
        """Get the free capacity for the inbound journey on a vehicle that moves according to a schedule in TEU.
        """
        if vehicle in self.free_capacity_for_inbound_journey_buffer:
            return self.free_capacity_for_inbound_journey_buffer[vehicle]

        large_scheduled_vehicle: LargeScheduledVehicle = vehicle.large_scheduled_vehicle
        total_moved_capacity_for_inbound_transportation_in_teu = large_scheduled_vehicle.moved_capacity
        free_capacity_in_teu = self._get_free_capacity_in_teu(
            vehicle=vehicle,
            maximum_capacity=total_moved_capacity_for_inbound_transportation_in_teu,
            container_counter=self._get_number_containers_for_inbound_journey
        )
        self.free_capacity_for_inbound_journey_buffer[vehicle] = free_capacity_in_teu
        return free_capacity_in_teu

    def get_free_capacity_for_outbound_journey(self, vehicle: Type[AbstractLargeScheduledVehicle]) -> float:
        """Get the free capacity for the outbound journey on a vehicle that moves according to a schedule in TEU.
        """
        assert self.transportation_buffer is not None, "First set the value!"
        assert -1 < self.transportation_buffer, "Must be larger than -1"

        if vehicle in self.free_capacity_for_outbound_journey_buffer:
            return self.free_capacity_for_outbound_journey_buffer[vehicle]

        # noinspection PyTypeChecker
        large_scheduled_vehicle: LargeScheduledVehicle = vehicle.large_scheduled_vehicle

        total_moved_capacity_for_onward_transportation_in_teu = \
            large_scheduled_vehicle.moved_capacity * (1 + self.transportation_buffer)
        maximum_capacity_of_vehicle = large_scheduled_vehicle.capacity_in_teu
        total_moved_capacity_for_onward_transportation_in_teu = min(
            total_moved_capacity_for_onward_transportation_in_teu,
            maximum_capacity_of_vehicle
        )

        free_capacity_in_teu = self._get_free_capacity_in_teu(
            vehicle=vehicle,
            maximum_capacity=total_moved_capacity_for_onward_transportation_in_teu,
            container_counter=self._get_number_containers_for_outbound_journey
        )
        self.free_capacity_for_outbound_journey_buffer[vehicle] = free_capacity_in_teu
        return free_capacity_in_teu

    # noinspection PyUnresolvedReferences
    @staticmethod
    def _get_free_capacity_in_teu(
            vehicle: Type[AbstractLargeScheduledVehicle],
            maximum_capacity: int,
            container_counter: Callable[[Type[AbstractLargeScheduledVehicle], ContainerLength], int]
    ) -> float:
        loaded_20_foot_containers = container_counter(vehicle, ContainerLength.twenty_feet)
        loaded_40_foot_containers = container_counter(vehicle, ContainerLength.forty_feet)
        loaded_45_foot_containers = container_counter(vehicle, ContainerLength.forty_five_feet)
        loaded_other_containers = container_counter(vehicle, ContainerLength.other)
        free_capacity_in_teu = (
                maximum_capacity
                - loaded_20_foot_containers * ContainerLength.get_factor(ContainerLength.twenty_feet)
                - loaded_40_foot_containers * ContainerLength.get_factor(ContainerLength.forty_feet)
                - loaded_45_foot_containers * ContainerLength.get_factor(ContainerLength.forty_five_feet)
                - loaded_other_containers * ContainerLength.get_factor(ContainerLength.other)
        )
        vehicle_name = vehicle.large_scheduled_vehicle.vehicle_name
        assert free_capacity_in_teu >= 0, f"vehicle {vehicle} of type {vehicle.get_mode_of_transport()} with the " \
                                          f"name '{vehicle_name}' " \
                                          f"is overloaded, " \
                                          f"free_capacity_in_teu: {free_capacity_in_teu} with " \
                                          f"maximum_capacity: {maximum_capacity}, " \
                                          f"loaded_20_foot_containers: {loaded_20_foot_containers}, " \
                                          f"loaded_40_foot_containers: {loaded_40_foot_containers}, " \
                                          f"loaded_45_foot_containers: {loaded_45_foot_containers} and " \
                                          f"loaded_other_containers: {loaded_other_containers}"
        return free_capacity_in_teu

    @classmethod
    def _get_number_containers_for_outbound_journey(
            cls,
            vehicle: Type[AbstractLargeScheduledVehicle],
            container_length: ContainerLength
    ) -> int:
        """Returns the number of containers on a specific vehicle of a specific container length that are picked up by
        the vehicle"""
        # noinspection PyTypeChecker
        large_scheduled_vehicle: LargeScheduledVehicle = vehicle.large_scheduled_vehicle
        number_loaded_containers = Container.select().where(
            (Container.picked_up_by_large_scheduled_vehicle == large_scheduled_vehicle)
            & (Container.length == container_length)
        ).count()
        return number_loaded_containers

    @classmethod
    def _get_number_containers_for_inbound_journey(
            cls,
            vehicle: AbstractLargeScheduledVehicle,
            container_length: ContainerLength
    ) -> int:
        """Returns the number of containers on a specific vehicle of a specific container length that are delivered by
        the vehicle"""

        large_scheduled_vehicle: LargeScheduledVehicle = vehicle.large_scheduled_vehicle
        number_loaded_containers = Container.select().where(
            (Container.delivered_by_large_scheduled_vehicle == large_scheduled_vehicle)
            & (Container.length == container_length)
        ).count()
        return number_loaded_containers

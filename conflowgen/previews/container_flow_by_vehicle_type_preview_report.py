from __future__ import annotations
import itertools
import logging
from typing import Dict

import plotly.graph_objects

from conflowgen.previews.container_flow_by_vehicle_type_preview import \
    ContainerFlowByVehicleTypePreview
from conflowgen.domain_models.data_types.mode_of_transport import ModeOfTransport
from conflowgen.reporting import AbstractReportWithPlotly


class ContainerFlowByVehicleTypePreviewReport(AbstractReportWithPlotly):
    """
    This preview report takes the data structure as generated by
    :class:`.ContainerFlowByVehicleTypePreview`
    and creates a comprehensible representation for the user, either as text or as a graph.
    The visual and table are expected to approximately look like in the
    `example ContainerFlowByVehicleTypePreviewReport \
    <notebooks/previews.ipynb#Container-Flow-By-Vehicle-Type-Preview-Report>`_.
    """

    report_description = """
    This report previews the container flow between vehicle types as defined by schedules and input distributions.
    """

    logger = logging.getLogger("conflowgen")

    def __init__(self):
        super().__init__()
        self.preview = ContainerFlowByVehicleTypePreview(
            start_date=self.start_date,
            end_date=self.end_date,
            transportation_buffer=self.transportation_buffer
        )

    def hypothesize_with_mode_of_transport_distribution(
            self,
            mode_of_transport_distribution: Dict[ModeOfTransport, Dict[ModeOfTransport, float]]
    ):
        self.preview.hypothesize_with_mode_of_transport_distribution(mode_of_transport_distribution)

    def get_report_as_text(
            self, **kwargs
    ) -> str:
        assert len(kwargs) == 0, f"No keyword arguments supported for {self.__class__.__name__}"

        inbound_to_outbound_flow = self._get_inbound_to_outbound_flow()

        # create string representation
        report = "\n"
        report += "vehicle type (from) "
        report += "vehicle type (to) "
        report += "required capacity (in TEU)"
        report += "\n"
        for vehicle_type_from, vehicle_type_to in itertools.product(self.order_of_vehicle_types_in_report, repeat=2):
            vehicle_type_from_as_text = str(vehicle_type_from).replace("_", " ")
            vehicle_type_to_as_text = str(vehicle_type_to).replace("_", " ")
            required_capacity = inbound_to_outbound_flow[vehicle_type_from][vehicle_type_to]
            report += f"{vehicle_type_from_as_text:<19} "
            report += f"{vehicle_type_to_as_text:<18} "
            report += f"{required_capacity:>25.1f}"
            report += "\n"

        report += "(rounding errors might exist)\n"
        return report

    def _get_inbound_to_outbound_flow(self) -> Dict[ModeOfTransport, Dict[ModeOfTransport, float]]:
        assert self.start_date is not None
        assert self.end_date is not None
        assert self.transportation_buffer is not None
        self.preview.update(
            start_date=self.start_date,
            end_date=self.end_date,
            transportation_buffer=self.transportation_buffer
        )
        # gather data
        inbound_to_outbound_flow = self.preview.get_inbound_to_outbound_flow()
        return inbound_to_outbound_flow

    def get_report_as_graph(self, **kwargs) -> plotly.graph_objects.Figure:
        """
        The container flow is represented by a Sankey diagram.

        Returns:
             The plotly figure of the Sankey diagram.

        .. note::
            At the time of writing, plotly comes with some shortcomings.

            * Sorting the labels on either the left or right side without recalculating the height of each bar is not
              possible, see https://github.com/plotly/plotly.py/issues/1732.
            * Empty nodes require special handling, see https://github.com/plotly/plotly.py/issues/3003 and the
              coordinates need to be :math:`0 < x,y < 1` (no equals!), see
              https://github.com/plotly/plotly.py/issues/3002.

            However, it seems to be the best available library for plotting Sankey diagrams that can be visualized,
            e.g., in a Jupyter Notebook.
        """
        assert len(kwargs) == 0, f"No keyword arguments supported for {self.__class__.__name__}"

        unit = "TEU"

        inbound_to_outbound_flow = self._get_inbound_to_outbound_flow()

        vehicle_types = [str(vehicle_type).replace("_", " ") for vehicle_type in inbound_to_outbound_flow.keys()]
        source_ids = list(range(len(vehicle_types)))
        target_ids = list(range(len(vehicle_types), 2 * len(vehicle_types)))
        value_ids = list(itertools.product(source_ids, target_ids))
        source_ids_with_duplication = [source_id for (source_id, _) in value_ids]
        target_ids_with_duplication = [target_id for (_, target_id) in value_ids]
        value = [
            inbound_to_outbound_flow[inbound_vehicle_type][outbound_vehicle_type]
            for inbound_vehicle_type in inbound_to_outbound_flow.keys()
            for outbound_vehicle_type in inbound_to_outbound_flow[inbound_vehicle_type].keys()
        ]

        if sum(value) == 0:
            self.logger.warning("No data available for plotting")

        inbound_labels = [
            str(inbound_vehicle_type).replace("_", " ").capitalize() + " inbound:<br>" + str(
                round(sum(inbound_to_outbound_flow[inbound_vehicle_type].values()), 2)) + " " + unit
            for inbound_vehicle_type in inbound_to_outbound_flow.keys()
        ]
        to_outbound_flow = [0 for _ in range(len(inbound_to_outbound_flow.keys()))]
        for inbound_vehicle_type, inbound_capacity in inbound_to_outbound_flow.items():
            for i, outbound_vehicle_type in enumerate(inbound_to_outbound_flow[inbound_vehicle_type].keys()):
                to_outbound_flow[i] += inbound_capacity[outbound_vehicle_type]
        outbound_labels = [
            str(outbound_vehicle_type).replace("_", " ").capitalize() + " outbound:<br>" + str(
                round(to_outbound_flow[i], 2)) + " " + unit
            for i, outbound_vehicle_type in enumerate(inbound_to_outbound_flow.keys())
        ]
        fig = plotly.graph_objects.Figure(
            data=[
                plotly.graph_objects.Sankey(
                    arrangement='perpendicular',
                    node={
                        'pad': 15,
                        'thickness': 20,
                        'line': {'color': 'black', 'width': 0.5},
                        'label': inbound_labels + outbound_labels,
                        'color': 'dimgray'
                    },
                    link={
                        'source': source_ids_with_duplication,
                        'target': target_ids_with_duplication,
                        'value': value
                    }
                )
            ]
        )

        fig.update_layout(
            title_text="Container flow from vehicle type A to vehicle type B as defined by inbound journeys<br>"
                       "and onward transportation distribution",
            font_size=10,
            width=900,
            height=700
        )
        return fig

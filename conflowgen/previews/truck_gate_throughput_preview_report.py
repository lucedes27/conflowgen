from abc import ABC
import typing
import pandas as pd

import matplotlib
from matplotlib import pyplot as plt

from conflowgen.domain_models.data_types.mode_of_transport import ModeOfTransport
from conflowgen.previews.truck_gate_throughput_preview import TruckGateThroughputPreview
from conflowgen.reporting import AbstractReportWithMatplotlib


class TruckGateThroughputPreviewReport(AbstractReportWithMatplotlib, ABC):
    """
    This preview report takes the data structure as generated by
    :class:`.TruckGateThroughputPreview`
    and creates a comprehensible representation for the user, either as text or as a graph.
    The visual and table are expected to approximately look like in the
    `example TruckGateThroughputPreviewReport <notebooks/previews.ipynb#Truck-Gate-Throughput-Preview-Report>`_.
    """

    report_description = """This report previews the average truck gate throughput throughout the week as defined by
    schedules and input distributions."""

    def __init__(self):
        super().__init__()
        self.preview = TruckGateThroughputPreview(
            start_date=self.start_date,
            end_date=self.end_date,
            transportation_buffer=self.transportation_buffer
        )

    def hypothesize_with_mode_of_transport_distribution(
            self,
            mode_of_transport_distribution: typing.Dict[ModeOfTransport, typing.Dict[ModeOfTransport, float]]
    ):
        self.preview.hypothesize_with_mode_of_transport_distribution(mode_of_transport_distribution)

    def _get_updated_preview(self) -> TruckGateThroughputPreview:
        assert self.start_date is not None
        assert self.end_date is not None
        assert self.transportation_buffer is not None
        self.preview.update(
            start_date=self.start_date,
            end_date=self.end_date,
            transportation_buffer=self.transportation_buffer
        )
        return self.preview

    def get_report_as_text(self, inbound: bool = True, outbound: bool = True, **kwargs) -> str:
        truck_distribution = self.preview.get_weekly_truck_arrivals(inbound, outbound)
        data = [
            {'minimum': float('inf'), 'maximum': 0, 'average': 0.0, 'sum': 0}
            for _ in range(8)  # Monday to Sunday plus week total
        ]

        fewest_trucks_in_a_day = float('inf')
        fewest_trucks_day = ''
        most_trucks_in_a_day = 0
        most_trucks_day = ''
        average_trucks_in_a_day = 0.0

        count = 0
        # Find min, max, and average for each day of the week
        for time in sorted(truck_distribution):
            day = time // 24
            if day == 0:
                count += 1
            data[day]['minimum'] = min(data[day]['minimum'], truck_distribution[time])
            data[day]['maximum'] = max(data[day]['maximum'], truck_distribution[time])
            data[day]['sum'] += truck_distribution[time]

        # Calculate average
        for day in range(7):
            data[day]['average'] = data[day]['sum'] / count
            data[7]['minimum'] = min(data[7]['minimum'], data[day]['minimum'])
            data[7]['maximum'] = max(data[7]['maximum'], data[day]['maximum'])
            data[7]['sum'] += data[day]['sum']
            if data[day]['sum'] < fewest_trucks_in_a_day:
                fewest_trucks_in_a_day = data[day]['sum']
                fewest_trucks_day = self.days_of_the_week[day]
            if data[day]['sum'] > most_trucks_in_a_day:
                most_trucks_in_a_day = data[day]['sum']
                most_trucks_day = self.days_of_the_week[day]
            most_trucks_in_a_day = max(most_trucks_in_a_day, data[day]['sum'])
            average_trucks_in_a_day += data[day]['sum']

        data[7]['average'] = data[7]['sum'] / (count * 7)
        average_trucks_in_a_day /= 7

        # Create a table with pandas for hourly view
        df = pd.DataFrame(data, index=self.days_of_the_week + ['Total'])
        df = df.round()
        df = df.astype(int)

        df = df.rename_axis('Day of the week')
        df = df.rename(columns={
            'minimum': 'Minimum (trucks/h)', 'maximum': 'Maximum (trucks/h)', 'average': 'Average (trucks/h)',
            'sum': 'Sum (trucks/24h)'})

        table_string = "Hourly view:\n" + df.to_string() + "\n"
        table_string += \
            "Fewest trucks in a day: " + str(int(fewest_trucks_in_a_day)) + " on " + fewest_trucks_day + "\n"
        table_string += \
            "Most trucks in a day: " + str(int(most_trucks_in_a_day)) + " on " + most_trucks_day + "\n"
        table_string += \
            "Average trucks per day: " + str(int(average_trucks_in_a_day))

        return table_string

    def get_report_as_graph(self, inbound: bool = True, outbound: bool = True, **kwargs) -> matplotlib.axes.Axes:
        # Retrieve the truck distribution
        truck_distribution = self.preview.get_weekly_truck_arrivals(inbound, outbound)

        # Plot the truck arrival distribution
        hour_in_week, value = zip(*list(sorted(truck_distribution.items())))
        weekday_in_week = [x / 24 + 1 for x in hour_in_week]

        fig, ax = plt.subplots(figsize=(15, 3))
        plt.plot(weekday_in_week, value)
        plt.xlim([1, 7])  # plot from Monday to Sunday
        ax.xaxis.grid(True, which="minor", color="lightgray")  # every hour
        ax.xaxis.grid(True, which="major", color="k")  # every day
        ax.xaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(1 / 24))  # every hour

        plt.title("Truck arrival distribution")
        ax.set_xticks(list(range(1, 8)))  # every day
        ax.set_xticklabels(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
        plt.xlabel("Week day")
        plt.ylabel("Number of trucks")

        return ax

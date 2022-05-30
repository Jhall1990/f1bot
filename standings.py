import requests
from datetime import datetime
from xml.etree import ElementTree

import utils


DRIVER_URL = "http://ergast.com/api/f1/{year}/driverStandings"


class Driver():
    def __init__(self, number, first_name, last_name, team, points):
        self.number = number
        self.first_name = first_name
        self.last_name = last_name
        self.team = team
        self.points = int(points)

    @staticmethod
    def from_xml(driver, constructor, points):
        first = last = num = team = ""

        for elem in list(driver):
            if elem.tag.endswith("GivenName"):
                first = elem.text
            elif elem.tag.endswith("FamilyName"):
                last = elem.text
            elif elem.tag.endswith("PermanentNumber"):
                num = elem.text

            if first and last and num:
                break

        for elem in list(constructor):
            if elem.tag.endswith("Name"):
                team = elem.text
            if team:
                break
        return Driver(num, first, last, team, points)


class DriverStandings():
    def __init__(self):
        self.drivers = []

    def to_text(self):
        self.drivers.sort(key=lambda x: x.points, reverse=True)
        cols = ("Place", "Name", "Team", "Points")
        tbl = utils.Table(cols)
        for idx, driver in enumerate(self.drivers):
            tbl.add_row(idx + 1, driver.last_name, driver.team, driver.points)
        return tbl.output()

    @staticmethod
    def from_xml(driver_xml):
        ds = DriverStandings()
        tree = ElementTree.fromstring(driver_xml)
        for standing_table in list(tree):
            for standing_list in list(standing_table):
                for driver_standing in list(standing_list):
                    points = driver_standing.get("points")
                    driver, constructor = list(driver_standing)
                    ds.drivers.append(Driver.from_xml(driver, constructor, points))
        return ds


class ConstructorStandings():
    def __init__(self):
        self.teams = {}

    @staticmethod
    def from_driver_standings(standings):
        cs = ConstructorStandings()
        for driver in standings.drivers:
            if driver.team not in cs.teams:
                cs.teams[driver.team] = 0
            cs.teams[driver.team] += driver.points
        return cs

    def to_text(self):
        cols = ("Place", "Team", "Points")
        tbl = utils.Table(cols)
        for idx, (team, points) in enumerate(sorted(self.teams.items(), key=lambda x: x[1], reverse=True)):
            tbl.add_row(idx + 1, team, points)
        return tbl.output()


def get_driver_standings():
    year = datetime.now().year
    response = requests.request("GET", DRIVER_URL.format(year=year), headers={}, data={})
    return DriverStandings.from_xml(response.text).to_text()


def get_constructor_standings():
    year = datetime.now().year
    response = requests.request("GET", DRIVER_URL.format(year=year), headers={}, data={})
    ds = DriverStandings.from_xml(response.text)
    return ConstructorStandings.from_driver_standings(ds).to_text()

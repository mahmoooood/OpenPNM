import json
import os
import pickle
from pathlib import Path

import jsonschema
import scipy as sp

from openpnm.core import logging
from openpnm.io import GenericIO
from openpnm.models.geometry import (pore_area, pore_volume, throat_area,
                                     throat_perimeter, throat_surface_area,
                                     throat_volume)
from openpnm.network import GenericNetwork

logger = logging.getLogger(__name__)


class JSONGraphFormat(GenericIO):
    r"""
    Class for reading and writing OpenPNM networks to JSON Graph Format (JGF).

    Notes
    -----
    The JGF standard must contain data formatted according to http://jsongraphformat.info and
    enforced by JSON schema validation.
    """

    @classmethod
    def __validate_json__(self, json_file):
        # Validate name of schema file
        relative_path_to_schema_filename = '../../utils/jgf_schema.pkl'
        schema_filename = Path(os.path.realpath(__file__), relative_path_to_schema_filename)
        schema_filename = self._parse_filename(filename=schema_filename, ext='pkl')

        # Load schema from pickle file
        with open(schema_filename, 'rb') as file:
            schema = pickle.load(file)

        # Validate JSON agains schema
        try:
            jsonschema.validate(json_file, schema)
            return True
        except jsonschema.exceptions.ValidationError:
            return False

    @classmethod
    def save(self, network, phases=[], filename=''):
        r"""
        Write the wetwork to disk as a JGF file.

        Parameters
        ----------
        network : OpenPNM Network Object

        filename : string
            Desired file name, defaults to network name if not given

        phases : list of phase objects ([])
            Phases that have properties we want to write to file

        """

    @classmethod
    def load(self, filename, project=None):
        r"""
        Loads the JGF file onto the given project.

        Parameters
        ----------
        filename : string
            The name of the file containing the data to import.  The formatting
            of this file is outlined below.

        project : OpenPNM Project object
            A GenericNetwork is created and added to the specified Project.
            If no Project object is supplied then one will be created and
            returned.

        Returns
        -------
        If no project object is supplied then one will be created and returned.

        """
        # Ensure input file is valid
        if not filename.endswith('.json'):
            raise(Exception('Error - JSONGraphFormat.load() expects a JSON file as input.'))
        filename = self._parse_filename(filename=filename, ext='json')

        # Load and validate input JSON
        with open(filename, 'r') as file:
            json_file = json.load(file)
            if not self.__validate_json__(json_file):
                raise(Exception('Error - ' + filename + ' is not in the JSON Graph Format.'))

        # Extract graph metadata from JSON
        number_of_nodes = json_file['graph']['metadata']['number_of_nodes']
        number_of_links = json_file['graph']['metadata']['number_of_links']

        # Extract node properties from JSON
        nodes = sorted(json_file['graph']['nodes'], key=lambda node: int(node['id']))
        x = sp.array([node['metadata']['node_coordinates']['x'] for node in nodes])
        y = sp.array([node['metadata']['node_coordinates']['y'] for node in nodes])
        z = sp.array([node['metadata']['node_coordinates']['z'] for node in nodes])

        # Extract link properties from JSON
        edges = sorted(json_file['graph']['edges'], key=lambda edge: int(edge['id']))
        source = sp.array([int(edge['source']) for edge in edges])
        target = sp.array([int(edge['target']) for edge in edges])
        link_length = sp.array([edge['metadata']['link_length'] for edge in edges])
        link_squared_radius = sp.array([edge['metadata']['link_squared_radius'] for edge in edges])

        # Generate network object
        network = GenericNetwork(Np=number_of_nodes, Nt=number_of_links)

        # Define primitive throat properties
        network['throat.length'] = link_length
        network['throat.conns'] = sp.column_stack([source, target])
        network['throat.diameter'] = 2.0 * sp.sqrt(link_squared_radius)

        # Define derived throat properties
        network['throat.area'] = throat_area.cylinder(network)
        network['throat.volume'] = throat_volume.cylinder(network)
        network['throat.perimeter'] = throat_perimeter.cylinder(network)
        network['throat.surface_area'] = throat_surface_area.cylinder(network)

        # Define primitive pore properties
        network['pore.index'] = sp.arange(number_of_nodes)
        network['pore.coords'] = sp.column_stack([x, y, z])
        network['pore.diameter'] = sp.zeros(number_of_nodes)

        # Define derived pore properties
        network['pore.area'] = pore_area.sphere(network)
        network['pore.volume'] = pore_volume.sphere(network)

        return network.project

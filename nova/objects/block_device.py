#    Copyright 2013 Red Hat Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time
from oslo_log import log as logging

from nova import block_device
from nova.cells import opts as cells_opts
from nova.cells import rpcapi as cells_rpcapi
from nova import db
from nova import exception
from nova.i18n import _
from nova import objects
from nova.objects import base
from nova.objects import fields


LOG = logging.getLogger(__name__)


_BLOCK_DEVICE_OPTIONAL_JOINED_FIELD = ['instance']
BLOCK_DEVICE_OPTIONAL_ATTRS = _BLOCK_DEVICE_OPTIONAL_JOINED_FIELD


def _expected_cols(expected_attrs):
    return [attr for attr in expected_attrs
                 if attr in _BLOCK_DEVICE_OPTIONAL_JOINED_FIELD]


# TODO(berrange): Remove NovaObjectDictCompat
@base.NovaObjectRegistry.register
class BlockDeviceMapping(base.NovaPersistentObject, base.NovaObject,
                         base.NovaObjectDictCompat):
    # Version 1.0: Initial version
    # Version 1.1: Add instance_uuid to get_by_volume_id method
    # Version 1.2: Instance version 1.14
    # Version 1.3: Instance version 1.15
    # Version 1.4: Instance version 1.16
    # Version 1.5: Instance version 1.17
    # Version 1.6: Instance version 1.18
    # Version 1.7: Add update_or_create method
    # Version 1.8: Instance version 1.19
    # Version 1.9: Instance version 1.20
    # Version 1.10: Changed source_type field to BlockDeviceSourceTypeField.
    # Version 1.11: Changed destination_type field to
    #               BlockDeviceDestinationTypeField.
    # Version 1.12: Changed device_type field to BlockDeviceTypeField.
    # Version 1.13: Instance version 1.21
    # Version 1.14: Instance version 1.22
    # Version 1.15: Instance version 1.23
    VERSION = '1.15'

    fields = {
        'id': fields.IntegerField(),
        'instance_uuid': fields.UUIDField(),
        'instance': fields.ObjectField('Instance', nullable=True),
        'source_type': fields.BlockDeviceSourceTypeField(nullable=True),
        'destination_type': fields.BlockDeviceDestinationTypeField(
                                nullable=True),
        'guest_format': fields.StringField(nullable=True),
        'device_type': fields.BlockDeviceTypeField(nullable=True),
        'disk_bus': fields.StringField(nullable=True),
        'boot_index': fields.IntegerField(nullable=True),
        'device_name': fields.StringField(nullable=True),
        'delete_on_termination': fields.BooleanField(default=False),
        'snapshot_id': fields.StringField(nullable=True),
        'volume_id': fields.StringField(nullable=True),
        'volume_size': fields.IntegerField(nullable=True),
        'image_id': fields.StringField(nullable=True),
        'no_device': fields.BooleanField(default=False),
        'connection_info': fields.StringField(nullable=True),
    }

    obj_relationships = {
        'instance': [('1.0', '1.13'), ('1.2', '1.14'), ('1.3', '1.15'),
                     ('1.4', '1.16'), ('1.5', '1.17'), ('1.6', '1.18'),
                     ('1.8', '1.19'), ('1.9', '1.20'), ('1.13', '1.21'),
                     ('1.14', '1.22'), ('1.15', '1.23')],
    }

    @staticmethod
    def _from_db_object(context, block_device_obj,
                        db_block_device, expected_attrs=None):
        if expected_attrs is None:
            expected_attrs = []
        for key in block_device_obj.fields:
            if key in BLOCK_DEVICE_OPTIONAL_ATTRS:
                continue
            block_device_obj[key] = db_block_device[key]
        if 'instance' in expected_attrs:
            my_inst = objects.Instance(context)
            my_inst._from_db_object(context, my_inst,
                                    db_block_device['instance'])
            block_device_obj.instance = my_inst

        block_device_obj._context = context
        block_device_obj.obj_reset_changes()
        return block_device_obj

    def _create(self, context, update_or_create=False):
        """Create the block device record in the database.

        In case the id field is set on the object, and if the instance is set
        raise an ObjectActionError. Resets all the changes on the object.

        Returns None

        :param context: security context used for database calls
        :param update_or_create: consider existing block devices for the
                instance based on the device name and swap, and only update
                the ones that match. Normally only used when creating the
                instance for the first time.
        """
        cell_type = cells_opts.get_cell_type()
        if cell_type == 'api':
            raise exception.ObjectActionError(
                    action='create',
                    reason='BlockDeviceMapping cannot be '
                           'created in the API cell.')

        if self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='create',
                                              reason='already created')
        updates = self.obj_get_changes()
        if 'instance' in updates:
            raise exception.ObjectActionError(action='create',
                                              reason='instance assigned')

        cells_create = update_or_create or None
        if update_or_create:
            db_bdm = db.block_device_mapping_update_or_create(
                    context, updates, legacy=False)
        else:
            db_bdm = db.block_device_mapping_create(
                    context, updates, legacy=False)

        self._from_db_object(context, self, db_bdm)
        # NOTE(alaski): bdms are looked up by instance uuid and device_name
        # so if we sync up with no device_name an entry will be created that
        # will not be found on a later update_or_create call and a second bdm
        # create will occur.
        if cell_type == 'compute' and db_bdm.get('device_name') is not None:
            cells_api = cells_rpcapi.CellsAPI()
            cells_api.bdm_update_or_create_at_top(
                    context, self, create=cells_create)

    @base.remotable
    def create(self):
        self._create(self._context)

    @base.remotable
    def update_or_create(self):
        self._create(self._context, update_or_create=True)

    @base.remotable
    def destroy(self):
        if not self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='destroy',
                                              reason='already destroyed')
        db.block_device_mapping_destroy(self._context, self.id)
        delattr(self, base.get_attrname('id'))

        cell_type = cells_opts.get_cell_type()
        if cell_type == 'compute':
            cells_api = cells_rpcapi.CellsAPI()
            cells_api.bdm_destroy_at_top(self._context, self.instance_uuid,
                                         device_name=self.device_name,
                                         volume_id=self.volume_id)

    @base.remotable
    def save(self):
        updates = self.obj_get_changes()
        if 'instance' in updates:
            raise exception.ObjectActionError(action='save',
                                              reason='instance changed')
        updates.pop('id', None)
        updated = db.block_device_mapping_update(self._context, self.id,
                                                 updates, legacy=False)
        if not updated:
            raise exception.BDMNotFound(id=self.id)
        self._from_db_object(self._context, self, updated)
        cell_type = cells_opts.get_cell_type()
        if cell_type == 'compute':
            create = False
            # NOTE(alaski): If the device name has just been set this bdm
            # likely does not exist in the parent cell and we should create it.
            # If this is a modification of the device name we should update
            # rather than create which is why None is used here instead of True
            if 'device_name' in updates:
                create = None
            cells_api = cells_rpcapi.CellsAPI()
            cells_api.bdm_update_or_create_at_top(self._context, self,
                    create=create)

    @base.remotable_classmethod
    def get_by_volume_id(cls, context, volume_id,
                         instance_uuid=None, expected_attrs=None):
        if expected_attrs is None:
            expected_attrs = []
        db_bdm = db.block_device_mapping_get_by_volume_id(
                context, volume_id, instance_uuid,  _expected_cols(expected_attrs))
        if not db_bdm:
            raise exception.VolumeBDMNotFound(volume_id=volume_id)
        # NOTE (ndipanov): Move this to the db layer into a
        # get_by_instance_and_volume_id method
        LOG.info("get_by_vlome_id ,volume_id: %s, instance_uuid: %s, bdm['instance_uuid']: %s", volume_id, instance_uuid, db_bdm['instance_uuid'])
        msg = "volume_id: %s, instance_uuid: %s, bdm['instance_uuid']: %s" % ( volume_id, instance_uuid, db_bdm['instance_uuid'])
        if instance_uuid and instance_uuid != db_bdm['instance_uuid']:
            raise exception.InvalidVolume(
                    reason=_("Volume does not belong to the "
                             "requested instance. %s" %(msg)))
        return cls._from_db_object(context, cls(), db_bdm,
                                   expected_attrs=expected_attrs)

    @property
    def is_root(self):
        return self.boot_index == 0

    @property
    def is_volume(self):
        return (self.destination_type ==
                    fields.BlockDeviceDestinationType.VOLUME)

    @property
    def is_image(self):
        return self.source_type == fields.BlockDeviceSourceType.IMAGE

    def get_image_mapping(self):
        return block_device.BlockDeviceDict(self).get_image_mapping()

    def obj_load_attr(self, attrname):
        if attrname not in BLOCK_DEVICE_OPTIONAL_ATTRS:
            raise exception.ObjectActionError(
                action='obj_load_attr',
                reason='attribute %s not lazy-loadable' % attrname)
        if not self._context:
            raise exception.OrphanedObjectError(method='obj_load_attr',
                                                objtype=self.obj_name())

        LOG.debug("Lazy-loading `%(attr)s' on %(name)s uuid %(uuid)s",
                  {'attr': attrname,
                   'name': self.obj_name(),
                   'uuid': self.uuid,
                   })
        self.instance = objects.Instance.get_by_uuid(self._context,
                                                     self.instance_uuid)
        self.obj_reset_changes(fields=['instance'])


@base.NovaObjectRegistry.register
class BlockDeviceMappingList(base.ObjectListBase, base.NovaObject):
    # Version 1.0: Initial version
    # Version 1.1: BlockDeviceMapping <= version 1.1
    # Version 1.2: Added use_slave to get_by_instance_uuid
    # Version 1.3: BlockDeviceMapping <= version 1.2
    # Version 1.4: BlockDeviceMapping <= version 1.3
    # Version 1.5: BlockDeviceMapping <= version 1.4
    # Version 1.6: BlockDeviceMapping <= version 1.5
    # Version 1.7: BlockDeviceMapping <= version 1.6
    # Version 1.8: BlockDeviceMapping <= version 1.7
    # Version 1.9: BlockDeviceMapping <= version 1.8
    # Version 1.10: BlockDeviceMapping <= version 1.9
    # Version 1.11: BlockDeviceMapping <= version 1.10
    # Version 1.12: BlockDeviceMapping <= version 1.11
    # Version 1.13: BlockDeviceMapping <= version 1.12
    # Version 1.14: BlockDeviceMapping <= version 1.13
    # Version 1.15: BlockDeviceMapping <= version 1.14
    # Version 1.16: BlockDeviceMapping <= version 1.15
    VERSION = '1.16'

    fields = {
        'objects': fields.ListOfObjectsField('BlockDeviceMapping'),
    }
    obj_relationships = {
        'objects': [('1.0', '1.0'), ('1.1', '1.1'), ('1.2', '1.1'),
                    ('1.3', '1.2'), ('1.4', '1.3'), ('1.5', '1.4'),
                    ('1.6', '1.5'), ('1.7', '1.6'), ('1.8', '1.7'),
                    ('1.9', '1.8'), ('1.10', '1.9'), ('1.11', '1.10'),
                    ('1.12', '1.11'), ('1.13', '1.12'), ('1.14', '1.13'),
                    ('1.15', '1.14'), ('1.16', '1.15')],
    }

    @base.remotable_classmethod
    def get_by_instance_uuid(cls, context, instance_uuid, use_slave=False):
        db_bdms = db.block_device_mapping_get_all_by_instance(
                context, instance_uuid, use_slave=use_slave)
        return base.obj_make_list(
                context, cls(), objects.BlockDeviceMapping, db_bdms or [])

    def root_bdm(self):
        try:
            return next(bdm_obj for bdm_obj in self if bdm_obj.is_root)
        except StopIteration:
            return


def block_device_make_list(context, db_list, **extra_args):
    return base.obj_make_list(context,
                              objects.BlockDeviceMappingList(context),
                              objects.BlockDeviceMapping, db_list,
                              **extra_args)


def block_device_make_list_from_dicts(context, bdm_dicts_list):
    bdm_objects = [objects.BlockDeviceMapping(context=context, **bdm)
                   for bdm in bdm_dicts_list]
    return BlockDeviceMappingList(objects=bdm_objects)

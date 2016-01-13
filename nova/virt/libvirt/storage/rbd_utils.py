# Copyright 2012 Grid Dynamics
# Copyright 2013 Inktank Storage, Inc.
# Copyright 2014 Mirantis, Inc.
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

import urllib

try:
    import rados
    import rbd
except ImportError:
    rados = None
    rbd = None

from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_service import loopingcall
from oslo_utils import excutils
from oslo_utils import units

from nova import exception
from nova.i18n import _
from nova.i18n import _LE
from nova.i18n import _LW
from nova import utils

LOG = logging.getLogger(__name__)


class RBDVolumeProxy(object):
    """Context manager for dealing with an existing rbd volume.

    This handles connecting to rados and opening an ioctx automatically, and
    otherwise acts like a librbd Image object.

    The underlying librados client and ioctx can be accessed as the attributes
    'client' and 'ioctx'.
    """
    def __init__(self, driver, name, pool=None, snapshot=None,
                 read_only=False):
        LOG.info("driver: %s, name: %s, pool: %s, snapshot: %s, read_only: %s" % (driver, name, pool, snapshot, read_only))
        self.name = name
        self.driver = driver
        self.pool = pool
        self.snapshot = snapshot
        self.read_only = read_only

        self.client = None 
        self.ioctx = None

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        pass

    def __getattr__(self, attrib):
        return getattr(self.volume, attrib)


class RADOSClient(object):
    """Context manager to simplify error handling for connecting to ceph."""
    def __init__(self, driver, pool=None):
        LOG.info("driver: %s, pool: %s" % (driver, pool))
        self.driver = driver
        self.cluster = None
        self.ioctx = None

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        self.driver._disconnect_from_rados(self.cluster, self.ioctx)

    @property
    def features(self):
        features = self.cluster.conf_get('rbd_default_features')
        if ((features is None) or (int(features) == 0)):
            features = rbd.RBD_FEATURE_LAYERING
        return int(features)


class RBDDriver(object):

    def __init__(self, pool, ceph_conf, rbd_user):
        self.pool = pool.encode('utf8')
        LOG.info("pool: %s, ceph_conf: %s, rbd_user: %s" % (pool, ceph_conf, rbd_user))
        # NOTE(angdraug): rados.Rados fails to connect if ceph_conf is None:
        # https://github.com/ceph/ceph/pull/1787
        self.ceph_conf = ceph_conf.encode('utf8') if ceph_conf else ''
        self.rbd_user = rbd_user.encode('utf8') if rbd_user else None
        #if rbd is None:
            #raise RuntimeError(_('rbd python libraries not found'))

    def _connect_to_rados(self, pool=None):
        LOG.info("pool: %s" % (pool))

    def _disconnect_from_rados(self, client, ioctx):
        # closing an ioctx cannot raise an exception
        pass

    def ceph_args(self):
        """List of command line parameters to be passed to ceph commands to
           reflect RBDDriver configuration such as RBD user name and location
           of ceph.conf.
        """
        args = []
        if self.rbd_user:
            args.extend(['--id', self.rbd_user])
        if self.ceph_conf:
            args.extend(['--conf', self.ceph_conf])
        return args

    def get_mon_addrs(self):
        args = ['ceph', 'mon', 'dump', '--format=json'] + self.ceph_args()
        out, _ = utils.execute(*args)
        lines = out.split('\n')
        if lines[0].startswith('dumped monmap epoch'):
            lines = lines[1:]
        monmap = jsonutils.loads('\n'.join(lines))
        addrs = [mon['addr'] for mon in monmap['mons']]
        hosts = []
        ports = []
        for addr in addrs:
            host_port = addr[:addr.rindex('/')]
            host, port = host_port.rsplit(':', 1)
            hosts.append(host.strip('[]'))
            ports.append(port)
        return hosts, ports

    def parse_url(self, url):
        prefix = 'rbd://'
        if not url.startswith(prefix):
            reason = _('Not stored in rbd')
            raise exception.ImageUnacceptable(image_id=url, reason=reason)
        pieces = map(urllib.unquote, url[len(prefix):].split('/'))
        if '' in pieces:
            reason = _('Blank components')
            raise exception.ImageUnacceptable(image_id=url, reason=reason)
        if len(pieces) != 4:
            reason = _('Not an rbd snapshot')
            raise exception.ImageUnacceptable(image_id=url, reason=reason)
        return pieces

    def _get_fsid(self):
        fsid = "96a91e6d-892a-41f4-8fd2-4a18c9002425"
        return fsid

    def is_cloneable(self, image_location, image_meta):
        url = image_location['url']
        try:
            fsid, pool, image, snapshot = self.parse_url(url)
        except exception.ImageUnacceptable as e:
            LOG.debug('not cloneable: %s', e)
            return False

        if self._get_fsid() != fsid:
            reason = '%s is in a different ceph cluster' % url
            LOG.debug(reason)
            return False

        if image_meta.get('disk_format') != 'raw':
            reason = ("rbd image clone requires image format to be "
                      "'raw' but image {0} is '{1}'").format(
                          url, image_meta.get('disk_format'))
            LOG.debug(reason)
            return False

        #todo 
        # check that we can read the image
        LOG.info("check we can read image: %s, pool: %s, snapshot: %s" % (image, pool, snapshot))

        return True

    def clone(self, image_location, dest_name):
        _fsid, pool, image, snapshot = self.parse_url(
                image_location['url'])
        LOG.info('cloning %(pool)s/%(img)s@%(snap)s' %
                  dict(pool=pool, img=image, snap=snapshot))
        #todo clone

    def size(self, name):
        LOG.info('get size of name %s' % (name))
        return 1024*1024*1024
        #todo

    def resize(self, name, size):
        """Resize RBD volume.

        :name: Name of RBD object
        :size: New size in bytes
        """
        LOG.debug('resizing rbd image %s to %d', name, size)
        #todo

    def exists(self, name, pool=None, snapshot=None):
        #todo
        pass

    def remove_image(self, name):
        """Remove RBD volume

        :name: Name of RBD volume
        """
        LOG.warn(_LW('image %(volume)s in pool %(pool)s  '
                    'to remove'),
                    {'volume': name, 'pool': self.pool})
        #todo


    def import_image(self, base, name):
        """Import RBD volume from image file.

        Uses the command line import instead of librbd since rbd import
        command detects zeroes to preserve sparseness in the image.

        :base: Path to image file
        :name: Name of RBD volume
        """
        args = ['--pool', self.pool, base, name]
        # Image format 2 supports cloning,
        # in stable ceph rbd release default is not 2,
        # we need to use it explicitly.
        args += ['--image-format=2']
        args += self.ceph_args()
        utils.execute('rbd', 'import', *args)

    def cleanup_volumes(self, instance):
        def _cleanup_vol(ioctx, volume, retryctx):
            LOG.info(_LW('rbd remove %(volume)s in pool %(pool)s '
                ''),
                {'volume': volume, 'pool': self.pool})
            #todo

        with RADOSClient(self, self.pool) as client:

            def belongs_to_instance(disk):
                return disk.startswith(instance.uuid)

            volumes = rbd.RBD().list(client.ioctx)
            for volume in filter(belongs_to_instance, volumes):
                # NOTE(danms): We let it go for ten seconds
                retryctx = {'retries': 10}
                timer = loopingcall.FixedIntervalLoopingCall(
                    _cleanup_vol, client.ioctx, volume, retryctx)
                timed_out = timer.start(interval=1).wait()
                if timed_out:
                    # NOTE(danms): Run this again to propagate the error, but
                    # if it succeeds, don't raise the loopingcall exception
                    try:
                        _cleanup_vol(client.ioctx, volume, retryctx)
                    except loopingcall.LoopingCallDone:
                        pass

    def get_pool_info(self):
        stats = {"kb": 1024*1024*1024*1024*2, "kb_avail": 1024*1024*1024*1024, "kb_used": 1000000}
        return {'total': stats['kb'] * units.Ki,
                    'free': stats['kb_avail'] * units.Ki,
                    'used': stats['kb_used'] * units.Ki}

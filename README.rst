OpenStack Nova README
=====================

1 首先在集群内安装nova 和 lich。

安装： 在controller 节点: glance_stor (github) cinder (github) nova (github)

在compute节点： cinder (github) nova (github) libvirtd （git) qemu (git)

并且在computer节点上定时修改/dev/shm/lich目录的用户为nova: 添加下面行到crontab */1 * * * * root chmod -R 777 /dev/shm/lich/

glance_stor:

2， 上传镜像

注意事项： a,镜像源必须采用：镜像地址 b,其他非必须项，采用默认值。

3， 云硬盘创建，删除。 创建时，输入磁盘名称和大小，其他为默认值。

4， 启动虚拟机实例

注意事项： a,云主机启动源 必须选用倒数第二个方式：（从镜像启动，创建一新卷） b,其他非必选项，采用默认值 或根据需要填写。 c,关机必须是‘关闭实例’。

4， 磁盘挂载 需要通过命令行的方式来挂载磁盘。 在使用命令行之前，需要先加载身份信息： 比如： [root@controller ~]# cat admin-openrc.sh export OS_PROJECT_DOMAIN_ID=default export OS_USER_DOMAIN_ID=default export OS_PROJECT_NAME=admin export OS_TENANT_NAME=admin export OS_USERNAME=admin export OS_PASSWORD=mds123 export OS_AUTH_URL=http://controller:35357/v3 export OS_IDENTITY_API_VERSION=3 export OS_IMAGE_API_VERSION=2

OpenStack Nova provides a cloud computing fabric controller,
supporting a wide variety of virtualization technologies,
including KVM, Xen, LXC, VMware, and more. In addition to
its native API, it includes compatibility with the commonly
encountered Amazon EC2 and S3 APIs.

OpenStack Nova is distributed under the terms of the Apache
License, Version 2.0. The full terms and conditions of this
license are detailed in the LICENSE file.

Nova primarily consists of a set of Python daemons, though
it requires and integrates with a number of native system
components for databases, messaging and virtualization
capabilities.

To keep updated with new developments in the OpenStack project
follow `@openstack <http://twitter.com/openstack>`_ on Twitter.

To learn how to deploy OpenStack Nova, consult the documentation
available online at:

   http://docs.openstack.org

For information about the different compute (hypervisor) drivers
supported by Nova, read this page on the wiki:

   https://wiki.openstack.org/wiki/HypervisorSupportMatrix

In the unfortunate event that bugs are discovered, they should
be reported to the appropriate bug tracker. If you obtained
the software from a 3rd party operating system vendor, it is
often wise to use their own bug tracker for reporting problems.
In all other cases use the master OpenStack bug tracker,
available at:

   http://bugs.launchpad.net/nova

Developers wishing to work on the OpenStack Nova project should
always base their work on the latest Nova code, available from
the master GIT repository at:

   https://git.openstack.org/cgit/openstack/nova

Developers should also join the discussion on the mailing list,
at:

   http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-dev

Any new code must follow the development guidelines detailed
in the HACKING.rst file, and pass all unit tests. Further
developer focused documentation is available at:

   http://docs.openstack.org/developer/nova/

For information on how to contribute to Nova, please see the
contents of the CONTRIBUTING.rst file.

-- End of broadcast

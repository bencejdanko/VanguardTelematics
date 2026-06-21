# The basic QNX makefile definition
ifndef QCONFIG
QCONFIG=qconfig.mk
endif
include $(QCONFIG)

# A short description of the binary
define PINFO
PINFO DESCRIPTION=Dump camera raw frames to disk without displaying viewfinder
endef

# The location to install the built binary on a target
INSTALLDIR = usr/bin

# Further QNX makefile definitions
include $(MKFILES_ROOT)/qmacros.mk
include $(MKFILES_ROOT)/qtargets.mk

# A space-separated list of libraries to be linked
LIBS += camapi

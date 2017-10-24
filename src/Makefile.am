#
#
#

AM_CXXFLAGS = -Wall -Wno-write-strings

lib_LTLIBRARIES = libuwoarouting.la

libuwoarouting_la_SOURCES = uwoarouting.cc uwoarouting.h initlib.cc

libuwoarouting_la_CPPFLAGS = @NS_CPPFLAGS@ @NSMIRACLE_CPPFLAGS@ @DESERT_CPPFLAGS@
libuwoarouting_la_LDFLAGS =  @NS_LDFLAGS@ @NSMIRACLE_LDFLAGS@ @DESERT_LDFLAGS@
libuwoarouting_la_LIBADD = @NS_LIBADD@ @NSMIRACLE_LIBADD@ @DESERT_LIBADD@

nodist_libuwoarouting_la_SOURCES = initTcl.cc

BUILT_SOURCES = initTcl.cc

CLEANFILES = initTcl.cc

TCL_FILES =  uwoarouting-init.tcl

initTcl.cc: Makefile $(TCL_FILES)
		cat $(VPATH)/$(TCL_FILES) | @TCL2CPP@ UWOARoutingInitTclCode > initTcl.cc

EXTRA_DIST = $(TCL_FILES)
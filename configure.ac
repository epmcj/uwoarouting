AC_INIT(uwoarouting,1.0)
AM_INIT_AUTOMAKE
AM_PROG_AR

AC_CONFIG_MACRO_DIR([m4])

AC_PROG_CXX
AC_PROG_MAKE_SET

AC_DISABLE_STATIC

AC_LIBTOOL_WIN32_DLL
AC_PROG_LIBTOOL

AC_PATH_NS_ALLINONE

AC_ARG_WITH_NSMIRACLE

CFLAGS="${CFLAGS=} -Wall"

AC_CHECK_NSMIRACLE

AC_ARG_WITH_DESERT
AC_ARG_WITH_DESERT_BUILD

AC_CHECK_DESERT([have_desert=yes],[have_desert=no])
if test x$have_desert != xyes ; then
  AC_MSG_ERROR([Could not find desert, is --with-desert set correctly?])
fi 

AC_DEFINE(CPP_NAMESPACE,std)

AC_CONFIG_FILES([
		Makefile
		src/Makefile
		m4/Makefile
		])
		
AC_OUTPUT
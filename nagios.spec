# $Id: nagios.spec 9310 2010-11-19 07:32:09Z cmr $
# Authority: dag
# Upstream: Ethan Galstad <nagios$nagios,org>

### FIXME: TODO: Add sysv script based on template. (remove cmd-file on start-up)
%define logmsg logger -t %{name}/rpm
%define logdir %{_localstatedir}/log/nagios

Summary: Open Source host, service and network monitoring program
Name: nagios
Version: 3.4.1
Release: 3%{?dist}
License: GPL
Group: Applications/System
URL: http://www.nagios.org/

Packager: Dag Wieers <dag@wieers.com>
Vendor: Dag Apt Repository, http://dag.wieers.com/apt/

Source0: http://prdownloads.sourceforge.net/sourceforge/nagios/nagios-%{version}.tar.gz
Source1: ftp://ftp.netbsd.org/pub/pkgsrc/packages/NetBSD-4.0/amd64/All/nagios-imagepak-base-20030219.tgz
Source2: daemon-init-redhat.in
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: gd-devel > 1.8
BuildRequires: zlib-devel
BuildRequires: libpng-devel
BuildRequires: libjpeg-devel
BuildRequires: perl-ExtUtils-Embed
BuildRequires: kernel-devel
BuildRequires: kernel-headers
Obsoletes: nagios-www <= %{version}
Requires: httpd
Requires: php

%description
Nagios is an application, system and network monitoring application.
It can escalate problems by email, pager or any other medium. It is
also useful for incident or SLA reporting.

Nagios is written in C and is designed as a background process,
intermittently running checks on various services that you specify.

The actual service checks are performed by separate "plugin" programs
which return the status of the checks to Nagios. The plugins are
located in the nagios-plugins package.

%package devel
Summary: Header files, libraries and development documentation for %{name}
Group: Development/Libraries
Requires: %{name} = %{version}-%{release}

%description devel
This package contains the header files, static libraries and development
documentation for %{name}. If you like to develop programs using %{name},
you will need to install %{name}-devel.

%prep
%setup

# /usr/local/nagios is hardcoded in many places
%{__perl} -pi.orig -e 's|/usr/local/nagios/var/rw|%{_localstatedir}/nagios/rw|g;' contrib/eventhandlers/submit_check_result

# copy our init-script over the one provided by upstream nut not for el3
%{!?el3:%{__cp} -f %{SOURCE2} daemon-init.in}

%build
%configure \
    --datadir="%{_datadir}/nagios" \
    --libexecdir="%{_libdir}/nagios/plugins" \
    --localstatedir="%{_localstatedir}/nagios" \
    --with-checkresult-dir="%{_localstatedir}/nagios/spool/checkresults" \
    --sbindir="%{_libdir}/nagios/cgi" \
    --sysconfdir="%{_sysconfdir}/nagios" \
    --with-cgiurl="/nagios/cgi-bin" \
    --with-command-user="apache" \
    --with-command-group="apache" \
    --with-gd-lib="%{_libdir}" \
    --with-gd-inc="%{_includedir}" \
    --with-htmurl="/nagios" \
    --with-init-dir="%{_initrddir}" \
    --with-lockfile="%{_localstatedir}/nagios/nagios.pid" \
    --with-mail="/bin/mail" \
    --with-nagios-user="nagios" \
    --with-nagios-group="nagios" \
    --enable-embedded-perl \
    --with-perlcache \
    --with-template-objects \
    --with-template-extinfo \
    --enable-event-broker
%{__make} %{?_smp_mflags} all

### Apparently contrib wants to do embedded-perl stuff as well and does not obey configure !
%{__make} %{?_smp_mflags} -C contrib

%install
%{__rm} -rf %{buildroot}
%{__make} install install-init install-commandmode install-config \
    DESTDIR="%{buildroot}" \
    INSTALL_OPTS="" \
    COMMAND_OPTS="" \
    INIT_OPTS=""

### Apparently contrib wants to do embedded-perl stuff as well and does not obey configure !
%{__make} install -C contrib \
    DESTDIR="%{buildroot}" \
    INSTALL_OPTS=""

%{__install} -d -m0755 %{buildroot}%{_libdir}/nagios/plugins/eventhandlers/
%{__cp} -afpv contrib/eventhandlers/* %{buildroot}%{_libdir}/nagios/plugins/eventhandlers/

%{__install} -d -m0755 %{buildroot}%{_includedir}/nagios/
%{__install} -p -m0644 include/*.h %{buildroot}%{_includedir}/nagios/

%{__install} -Dp -m0644 sample-config/httpd.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/nagios.conf

### FIX log-paths
%{__perl} -pi -e '
        s|log_file.*|log_file=%{logdir}/nagios.log|;
        s|log_archive_path=.*|log_archive_path=%{logdir}/archives|;
        s|debug_file=.*|debug_file=%{logdir}/nagios.debug|;
   ' %{buildroot}%{_sysconfdir}/nagios/nagios.cfg

### make logdirs
%{__mkdir} -p %{buildroot}%{logdir}/
%{__mkdir} -p %{buildroot}%{logdir}/archives/

### Install logos
%{__mkdir} -p %{buildroot}%{_datadir}/nagios/images/logos
tar -xvz -C %{buildroot}%{_prefix} --exclude=+* -f %{SOURCE1}

%pre
if ! /usr/bin/id nagios &>/dev/null; then
    /usr/sbin/useradd -r -d %{logdir} -s /bin/sh -c "nagios" nagios || \
        %logmsg "Unexpected error adding user \"nagios\". Aborting installation."
fi
if ! /usr/bin/getent group nagiocmd &>/dev/null; then
    /usr/sbin/groupadd nagiocmd &>/dev/null || \
        %logmsg "Unexpected error adding group \"nagiocmd\". Aborting installation."
fi

%post
/sbin/chkconfig --add nagios

if /usr/bin/id apache &>/dev/null; then
    if ! /usr/bin/id -Gn apache 2>/dev/null | grep -q nagios ; then
        /usr/sbin/usermod -a -G nagios,nagiocmd apache &>/dev/null
    fi
else
    %logmsg "User \"apache\" does not exist and is not added to group \"nagios\". Sending commands to Nagios from the command CGI is not possible."
fi

if [ -f %{_sysconfdir}/httpd/conf/httpd.conf ]; then
    if ! grep -q "Include .*/nagios.conf" %{_sysconfdir}/httpd/conf/httpd.conf; then
        echo -e "\n# Include %{_sysconfdir}/httpd/conf.d/nagios.conf" >> %{_sysconfdir}/httpd/conf/httpd.conf
#       /sbin/service httpd restart
    fi
fi

%preun
if [ $1 -eq 0 ]; then
    /sbin/service nagios stop &>/dev/null || :
    /sbin/chkconfig --del nagios
fi

%postun
if [ $1 -eq 0 ]; then
    /usr/sbin/userdel nagios || %logmsg "User \"nagios\" could not be deleted."
    /usr/sbin/groupdel nagios || %logmsg "Group \"nagios\" could not be deleted."
fi
/sbin/service nagios condrestart &>/dev/null || :

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-, root, root, 0755)
%doc Changelog INSTALLING LICENSE README UPGRADING
%config(noreplace) %{_sysconfdir}/httpd/conf.d/nagios.conf
%config %{_initrddir}/nagios
%{_bindir}/convertcfg
%attr(755,nagios,nagios) %{_bindir}/nagios
%{_bindir}/nagiostats
%{_bindir}/p1.pl
%{_bindir}/mini_epn
%{_bindir}/new_mini_epn
%{_libdir}/nagios/
%{_datadir}/nagios/

#%defattr(-, root, nagios, 0755)
#%config(noreplace) %{_sysconfdir}/nagios/private/

%defattr(-, nagios, nagios, 0755)
%dir %{_sysconfdir}/nagios/
%config(noreplace) %{_sysconfdir}/nagios/*.cfg
%config(noreplace) %{_sysconfdir}/nagios/objects
%{_localstatedir}/nagios/
%{_localstatedir}/nagios/spool/
%{logdir}/

%defattr(-, nagios, apache, 2755)
%{_localstatedir}/nagios/rw/

%files devel
%defattr(-, root, root, 0755)
%{_includedir}/nagios/

%changelog
* Thu Jul  5 2010 Eugene Vilensky <evilensky@gmail.com> - 3.4.1
- Rebuilt from fresh 3.4.1 tarball

* Fri Nov 19 2010 Christoph Maser <cmaser@gmx.de> - 3.2.3-3
- adapt the extraction for nagios-imagepak-base from BSD

* Tue Nov 09 2010 Christoph Maser <cmaser@gmx.de> - 3.2.3-2
- remove -p ${pidfile} from killproc in reload el4 killproc doesnot support -p

* Fri Nov 05 2010 Christoph Maser <cmaser@gmx.de> - 3.2.3-1
- Updated to version 3.2.3.
- Use orignial init script on el3

* Tue Oct 05 2010 Dag Wieers <dag@wieers.com> - 3.2.2-1
- Updated to release 3.2.2.

* Sat Aug 29 2010 Christoph Maser <cmr@financial.com> - 3.2.1-6
- remove "-p pidfile" from call to killproc in initscript to make
  it el4 compatible

* Fri Jun 18 2010 Christoph Maser <cmr@financial.com> - 3.2.1-5
- Run configtest with correct user instead of root
- Use --user in init script call to daemon function
- Change owner of /usr/bin/nagios to nagios

* Wed Jun 02 2010 Christoph Maser <cmr@financial.com> - 3.2.1-4
- Add configtest to initscript

* Tue May 11 2010 Christoph Maser <cmr@financial.com> - 3.2.1-3
- Roll our own init-script
- Move pid file to a location where nagios user has access

* Fri May 07 2010 Yury V. Zaytsev <yury@shurup.com> - 3.2.1-2
- Fixed Apache group assignement (Catalin Bucur).
- Cleaned up old options.

* Sun Mar 21 2010 Dag Wieers <dag@wieers.com> - 3.2.1-1
- Updated to release 3.2.1.

* Thu Aug 12 2009 Christoph Maser <cmr$financial,com> - 3.2.0-1
- Updated to release 3.2.0.

* Mon Aug 03 2009 Christoph Maser <cmr$financial,com> - 3.1.2-1
- Updated to release 3.1.2.

* Mon Jan 26 2009 Christoph Maser <cmr$financial,com> - 3.1.0-1
- Updated to release 3.1.0.

* Thu Dec 02 2008 Christoph Maser <cmr$financial,com> - 3.0.6-1
- Updated to release 3.0.6.

* Thu Nov 06 2008 Christoph Maser <cmr$financial,com> - 3.0.5-1
- Updated to release 3.0.5.

* Tue Oct 21 2008 Christoph Maser <cmr$financial,com> - 3.0.4-1
- Updated to release 3.0.4.

* Wed Oct 10 2008 Christoph Maser <cmr$financial,com> - 3.0.3-1
- Updated to release 3.0.3.
- Set localstatedir to ${_localstatedir}.
- Because of the previous modify installed configs to put logs in %{logdir}.

* Thu May 22 2008 Dag Wieers <dag@wieers.com> - 2.12-1
- Updated to release 2.12.

* Thu Mar 13 2008 Dag Wieers <dag@wieers.com> - 2.11-1
- Updated to release 2.11.
- Fixed a wrong reference to /usr/local. (Christophe Sahut)

* Wed Oct 24 2007 Christoph Maser <cmr@financial.com> - 2.10-1
- Updated to release 2.10.

* Sun Apr 15 2007 Dag Wieers <dag@wieers.com> - 2.9-1
- Updated to release 2.9.

* Sat Mar 10 2007 Dag Wieers <dag@wieers.com> - 2.8-1
- Updated to release 2.8.

* Wed Jan 24 2007 Dag Wieers <dag@wieers.com> - 2.7-1
- Updated to release 2.7.

* Mon Dec 11 2006 Dag Wieers <dag@wieers.com> - 2.6-1
- Updated to release 2.6.

* Wed Jul 19 2006 Dag Wieers <dag@wieers.com> - 2.5-1
- Updated to release 2.5.

* Fri Jun 02 2006 Dag Wieers <dag@wieers.com> - 2.4-2
- Make nagios owner of /etc/nagios. (Christop Maser)
- Updated to release 2.4.

* Mon May 29 2006 Dag Wieers <dag@wieers.com> - 2.3.1-2
- Make nagios owner of /etc/nagios. (Christop Maser)

* Wed May 17 2006 Dag Wieers <dag@wieers.com> - 2.3.1-1
- Updated to release 2.3.1.

* Wed May 03 2006 Dag Wieers <dag@wieers.com> - 2.3-1
- Updated to release 2.3.

* Sat Apr 08 2006 Dag Wieers <dag@wieers.com> - 2.2-1
- Updated to release 2.2.

* Tue Mar 28 2006 Dag Wieers <dag@wieers.com> - 2.1-1
- Updated to release 2.1.

* Wed Feb 08 2006 Dag Wieers <dag@wieers.com> - 2.0-2
- Fixed the nagiocmd group creation. (Rick Johnson)
- Added _without_perlcache macro. (Rick Johnson)

* Wed Feb 08 2006 Dag Wieers <dag@wieers.com> - 2.0-1
- Updated to release 2.0.

* Thu Jan 12 2006 Dag Wieers <dag@wieers.com> - 2.0-0.rc2
- Updated to release 2.0rc2.

* Sun Jan 01 2006 Dag Wieers <dag@wieers.com> - 2.0-0.rc1
- Updated to release 2.0rc1.

* Mon Dec 12 2005 Dag Wieers <dag@wieers.com> - 2.0-0.b6.1
- Updated to release 2.0b6.

* Fri Aug 05 2005 Dag Wieers <dag@wieers.com> - 2.0-0.b4.1
- Updated to release 2.0b4.

* Mon May 23 2005 Dag Wieers <dag@wieers.com> - 2.0-0.b3.1
- Use the actual 2.0b3 sourcecode, sigh. (Cameron Pitt-Downton)

* Wed May 18 2005 Dag Wieers <dag@wieers.com> - 2.0-0.b3
- Updated to release 2.0b3.

* Mon Feb 21 2005 Tim Verhoeven <dj@rootshell.be> - 2.0-0.b2
- Updated to release 2.0b2.

* Sun Jan 02 2005 Dag Wieers <dag@wieers.com> - 2.0-0.b1
* Updated to release 2.0b1.

* Fri Nov 26 2004 Dag Wieers <dag@wieers.com> - 1.2-1
* Fixed %%{_libdir} in httpd nagios.conf. (Thomas Zehetbauer)

* Wed Feb 11 2004 Dag Wieers <dag@wieers.com> - 1.2-0
- Added embedded perl patch for perl > 5.8. (Stanley Hopcroft)
- Updated to release 1.2.

* Wed Jan 28 2004 Dag Wieers <dag@wieers.com> - 1.1-6
- Fixed the longstanding nagios.cmd problem. (Magnus Stenman)

* Wed Oct 29 2003 Dag Wieers <dag@wieers.com> - 1.1-5
- Fixed resource.cfg location from nagios.cfg. (Ragnar Wisloff)
- Cleaned up perl one-liners.

* Wed Oct 08 2003 Dag Wieers <dag@wieers.com> - 1.1-4
- Removed --with-file-perfdata, use default. (Erik De Cock)

* Mon Aug 25 2003 Dag Wieers <dag@wieers.com> - 1.1-3
- Fixed the missing @MAIL_PROG@ problem in misccommands.cfg.

* Mon Aug 18 2003 Dag Wieers <dag@wieers.com> - 1.1-2
- Let %pre silently check for user nagios.
- Added base imagepak.

* Sat Jul 12 2003 Dag Wieers <dag@wieers.com> - 1.1-1
- Disabled embedded perl.

* Wed Jun 04 2003 Dag Wieers <dag@wieers.com> - 1.1-0
- Updated to release 1.1.

* Tue Jun 03 2003 Dag Wieers <dag@wieers.com> - 1.0-1
- Don't restart webserver.

* Sun Feb 16 2003 Dag Wieers <dag@wieers.com> - 1.0-0
- Initial package. (using DAR)

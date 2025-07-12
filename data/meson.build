desktop_conf = configuration_data()
desktop_conf.set('ICON', APPLICATION_ID)

desktop_file = i18n.merge_file(
        input: configure_file(
          input: 'io.github.wartybix.Constrict.desktop.in',
          output: APPLICATION_ID + '.desktop.in',
          configuration: desktop_conf
        ),
       output: APPLICATION_ID + '.desktop',
         type: 'desktop',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'applications'
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

appdata_conf = configuration_data()
appdata_conf.set('APPLICATION_ID', APPLICATION_ID)

appstream_file = i18n.merge_file(
        input: configure_file(
          input: 'io.github.wartybix.Constrict.metainfo.xml.in',
          output: APPLICATION_ID + '.metainfo.xml.in',
          configuration: appdata_conf
        ),
       output: APPLICATION_ID + '.metainfo.xml',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

appstreamcli = find_program('appstreamcli', required: false, disabler: true)
test('Validate appstream file', appstreamcli,
     args: ['validate', '--no-net', '--explain', appstream_file])

gschema_conf = configuration_data()
gschema_conf.set('APPLICATION_ID', APPLICATION_ID)
gschema_conf.set('PREFIX', PREFIX)

install_data(
  configure_file(
    input: 'io.github.wartybix.Constrict.gschema.xml.in',
    output: APPLICATION_ID + '.gschema.xml',
    configuration: gschema_conf
  ),
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas'
)

compile_schemas = find_program('glib-compile-schemas', required: false, disabler: true)
test('Validate schema file',
     compile_schemas,
     args: ['--strict', '--dry-run', meson.current_source_dir()])


service_conf = configuration_data()
service_conf.set('bindir', get_option('prefix') / get_option('bindir'))
service_conf.set('APPLICATION_ID', APPLICATION_ID)
configure_file(
  input: 'io.github.wartybix.Constrict.service.in',
  output: APPLICATION_ID + '.service',
  configuration: service_conf,
  install_dir: get_option('datadir') / 'dbus-1' / 'services'
)

subdir('icons')

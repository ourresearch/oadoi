module.exports = function (grunt) {

  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-html2js');

  // Default task.
  grunt.registerTask('default', ['build']);
  grunt.registerTask('build', ['clean','html2js','concat']);



  // Project configuration.
  grunt.initConfig({
    distdir: 'dist',
    pkg: grunt.file.readJSON('package.json'),
    banner:
    '/* yay impactstory */\n',



    src: {
      js: ['src/**/*.js', 'dist/templates/*.js'],
      html: ['src/index.html'],
      tpl: {
        app: ['src/**/*.tpl.html']
      }
    },



    clean: ['<%= distdir %>/*'],

    html2js: {
      app: {
        options: {
          base: 'src'
        },
        src: ['src/**/*.tpl.html'],
        dest: 'dist/templates.js',
        module: 'templates.app'
      }
    },

    concat:{
      dist:{
        options: {
          banner: "<%= banner %>"
        },
        src:['src/**/*.js', 'dist/templates.js'],
        dest:'<%= distdir %>/ti.js'
      },
      angular: {
        src:['vendor/angular/*.js'],
        dest: '<%= distdir %>/angular-libs.js'
      }
    },


    watch:{
      all: {
        files:['src/*'],
        tasks:['default']
      }
    }
  });

};
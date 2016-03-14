angular.module('app', [
  // external libs

  'ngRoute',
  'ngMessages',
  'satellizer',

  'ngResource',
  'ngSanitize',

  'templates.app',  // this is how it accesses the cached templates in ti.js

  'staticPages',

  'badgeDefs',
  'personPage',
  'settingsPage',
  'badgePage',

  'numFormat',

]);




angular.module('app').config(function ($routeProvider,
                                       $authProvider,
                                       $locationProvider) {


  $locationProvider.html5Mode(true);


    $authProvider.oauth2({
      name: "orcid",
      url: "/api/auth/orcid",
      clientId: "APP-PF0PDMP7P297AU8S",
      redirectUri: window.location.origin,
      authorizationEndpoint: "https://orcid.org/oauth/authorize",

      defaultUrlParams: ['response_type', 'client_id', 'redirect_uri'],
      requiredUrlParams: ['scope', 'show_login'],
      scope: ['/authenticate'],
      responseType: 'code',
      showLogin: 'true',
      responseParams: {
        code: 'code',
        clientId: 'clientId',
        redirectUri: 'redirectUri'
      }
    });
});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $location) {





  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-23384030-3', 'auto');



  $rootScope.$on('$routeChangeStart', function(next, current){
  })
  $rootScope.$on('$routeChangeSuccess', function(next, current){
    window.scrollTo(0, 0)
    ga('send', 'pageview', { page: $location.url() });

  })
  $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
    console.log("$routeChangeError")
    $location.path("/")
    window.scrollTo(0, 0)
  });


  // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
  (function(o) {
    Number.getOrdinalFor = function(intNum, includeNumber) {
      return (includeNumber ? intNum : "")
        + (o[((intNum = Math.abs(intNum % 100)) - 20) % 10] || o[intNum] || "th");
    };
  })([,"st","nd","rd"]);




  /*
  this lets you change the args of the URL without reloading the whole view. from
     - https://github.com/angular/angular.js/issues/1699#issuecomment-59283973
     - http://joelsaupe.com/programming/angularjs-change-path-without-reloading/
     - https://github.com/angular/angular.js/issues/1699#issuecomment-60532290
  */
  var original = $location.path;
  $location.path = function (path, reload) {
      if (reload === false) {
          var lastRoute = $route.current;
          var un = $rootScope.$on('$locationChangeSuccess', function () {
              $route.current = lastRoute;
              un();
          });
        $timeout(un, 500)
      }
      return original.apply($location, [path]);
  };




});


angular.module('app').controller('AppCtrl', function(
  $rootScope,
  $scope,
  $location,
  NumFormat,
  $auth,
  $sce){

    $scope.auth = $auth
    $scope.numFormat = NumFormat
    $scope.moment = moment // this will break unless moment.js loads over network...

    $scope.global = {}
    $scope.global.isLandingPage = false

    $rootScope.$on('$routeChangeStart', function(next, current){
        $scope.global.isLandingPage = false
    })

    $scope.trustHtml = function(str){
        console.log("trusting html:", str)
        return $sce.trustAsHtml(str)
    }


    // pasted from teh landing page
    $scope.navAuth = function () {
        console.log("authenticate!")

        $auth.authenticate("orcid")
            .then(function(resp){
                var orcid_id = $auth.getPayload()['sub']
                console.log("you have successfully logged in!", resp, $auth.getPayload())

                // take the user to their profile.
                $location.path("/u/" + orcid_id)

            })
            .catch(function(error){
                console.log("there was an error logging in:", error)
            })
    };



});


angular.module('badgePage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/badge/:badgeName', {
            templateUrl: 'badge-page/badge-page.tpl.html',
            controller: 'badgePageCtrl',
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                },
                badgesResp: function($http, $route, BadgeDefs){
                    console.log("loaded the badge defs in the route def")
                    return BadgeDefs.load()
                }
            }
        })
    })



    .controller("badgePageCtrl", function($scope,
                                           $routeParams,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){
        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs

        var badges = Person.getBadgesWithConfigs(BadgeDefs.d)

        var badge = _.findWhere(badges, {name: $routeParams.badgeName})
        $scope.badge = badge
        $scope.badgeProducts = _.filter(Person.d.products, function(product){
            return _.contains(badge.dois, product.doi)
        })

        console.log("we found these products fit the badge", $scope.badgeProducts)





        console.log("loaded the badge page!", $scope.person, $scope.badgeDefs)








    })




angular.module("filterService", [])

.factory("FilterService", function($location){

    var filters = {
      only_academic: "true",
      language: "python",
      tag: null,
      type: "pacakges"
    }

    var setFromUrl = function(){
      filters.only_academic = $location.search().only_academic
      filters.tag = $location.search().tag
      filters.language = $location.search().language
      filters.type = $location.search().type
      if (!filters.language){
        set("language", "python")
      }
      if (!filters.type){
        set("type", "people")
      }
      console.log("set filters from url", filters)
    }

    var set = function(k, v){
      filters[k] = v
      $location.search(k, v)
    }
    var toggle = function(k){
      // for booleans
      if (filters[k]) {
        filters[k] = null
      }
      else {
        filters[k] = "true"  // must be string or won't show up in url
      }
      $location.search(k, filters[k])
    }

    var unset = function(k){
      filters[k] = null
    }
    var unsetAll = function(){
        console.log("unset all!")
        _.each(filters, function(v, k){
            filters[k] = null
            $location.search(k, null)
        })
    }

    var asQueryStr = function(){
      var ret = []
      _.each(filters, function(v, k){
        if (v){
          ret.push(k + "=" + v)
        }
      })
      return ret.join("&")
    }


  return {
    d: filters,
    set: set,
    toggle: toggle,
    unset: unset,
    setFromUrl: setFromUrl,
    asQueryStr: asQueryStr,
    unsetAll: unsetAll
  }
});
angular.module('footer', [
])



    .controller("footerCtrl", function($scope,
                                       $location,
                                       $rootScope,
                                       FormatterService,
                                       FilterService,
                                       $http){


        //$scope.hideEmailSignup = !!$.cookie("hideEmailSignup")
        //
        //
        //$scope.dismissEmailSignup = function(){
        //    console.log("dismiss the signup")
        //    $scope.hideEmailSignup = true
        //    !$.cookie("hideEmailSignup", true)
        //}



    })







angular.module("formatterService", [])

    .factory("FormatterService", function($location){

        var commas = function(x) { // from stackoverflow
            if (!x) {
                return x
            }
            var parts = x.toString().split(".");
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            return parts.join(".");
        }

        var short = function(num, fixedAt){
            if (typeof num === "string"){
                return num  // not really a number
            }

            // hack for dealing with pagerank
            if (fixedAt){
                return num.toFixed(fixedAt)
            }


            // from http://stackoverflow.com/a/14994860/226013
            if (num === null){
                return 0
            }
            if (num === 0){
                return 0
            }

            if (num >= 1000000) {
                return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
            }
            if (num >= 100000) { // no decimal if greater than 100thou
                return (num / 1000).toFixed(0).replace(/\.0$/, '') + 'k';
            }

            if (num >= 1000) {
                return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
            }


            if (num < 1) {
                return Math.round(num * 100) / 100
            }

            return Math.floor(num);
        }

        var round = function(num){
            return Math.round(num)
        }

        var doubleUrlEncode = function(str){
            return encodeURIComponent( encodeURIComponent(str) )
        }

        // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
        var ordinal = function(n) {
            n = Math.round(n)
            var s=["th","st","nd","rd"],
                v=n%100;
            return n+(s[(v-20)%10]||s[v]||s[0]);
        }

        return {
            short: short,
            commas: commas,
            round: round,
            ordinal: ordinal,
            doubleUrlEncode: doubleUrlEncode

        }
    });
angular.module('header', [
  ])



  .controller("headerCtrl", function($scope,
                                     $location,
                                     $rootScope,
                                     FormatterService,
                                     FilterService,
                                     $http){



    $scope.searchResultSelected = ''
    $scope.format = FormatterService
    $scope.foo = 42

    $rootScope.$on('$routeChangeSuccess', function(next, current){
      $scope.searchResultSelected = ''
      document.getElementById("search-box").blur()
    })
    $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
      $scope.searchResultSelected = ''
      document.getElementById("search-box").blur()
    });


    $scope.onSelect = function(item ){
      console.log("select!", item)
      if (item.type=='pypi_project') {
        $location.path("package/python/" + item.name)
      }
      else if (item.type=='cran_project') {
        $location.path("package/r/" + item.name)
      }
      else if (item.type=='person') {
        $location.path("person/" + item.id)
      }
      else if (item.type=='tag') {
        FilterService.unsetAll()
        $location.path("tag/" + encodeURIComponent(encodeURIComponent( item.name)))
      }
    }

    $scope.doSearch = function(val){
      console.log("doing search")
      return $http.get("/api/search/" + val)
        .then(
          function(resp){
            //return resp.data.list
            return _.map(resp.data.list, function(match){
              //return match
              match.urlName = encodeURIComponent(encodeURIComponent(match.name))
              return match
            })

            var names = _.pluck(resp.data.list, "name")
            console.log(names)
            return names
          }
        )
    }

  })

.controller("searchResultCtrl", function($scope, $sce){


    $scope.trustHtml = function(str){
      console.log("trustHtml got a thing", str)

      return $sce.trustAsHtml(str)
    }




  })







angular.module('packagePage', [
    'directives.badge',
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/package/:language/:package_name', {
            templateUrl: 'package-page/package-page.tpl.html',
            controller: 'PackagePageCtrl',
            resolve: {
                packageResp: function($http, $route, PackageResource){
                    return PackageResource.get({
                        namespace: $route.current.params.language,
                        name: $route.current.params.package_name
                    }).$promise
                }
            }
        })
    })



    .controller("PackagePageCtrl", function($scope,
                                            $routeParams,
                                            FormatterService,
                                            packageResp){
        $scope.package = packageResp
        $scope.format = FormatterService
        $scope.depNode = packageResp.rev_deps_tree

        console.log("package page!", $scope.package)

        $scope.apiOnly = function(){
            alert("Sorry, we're still working on this! In the meantime, you can view the raw data via our API.")
        }










    })




angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                },
                badgesResp: function($http, $route, BadgeDefs){
                    console.log("loaded the badge defs in the route def")
                    return BadgeDefs.load()
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){
        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs

        console.log("retrieved the person", $scope.person)


        var badgesWithConfigs = Person.getBadgesWithConfigs(BadgeDefs.d)

        var groupedByLevel = _.groupBy(badgesWithConfigs, "level")

        // ok the badge columns are all set up, put in scope now.
        $scope.badgeCols = [
            {level: "gold", list: groupedByLevel.gold},
            {level: "silver", list: groupedByLevel.silver},
            {level: "bronze", list: groupedByLevel.bronze}
        ]










    })




angular.module('resourcesModule', [])
  .factory('Leaders', function($resource) {
    return $resource('api/leaderboard')
  })


  .factory('PackageResource', function($resource) {
    return $resource('/api/package/:namespace/:name')
  })
angular.module('articleService', [
  ])



  .factory("ArticleService", function($http,
                                      $timeout,
                                      $location){

    var data = {}

    function getArticle(pmid){
      var url = "api/article/" + pmid
      console.log("getting article", pmid)
      return $http.get(url).success(function(resp){
        console.log("got response for api/article/" + pmid, resp)
        data.article = resp
      })
    }

    return {
      data: data,
      getArticle: getArticle
    }


  })
angular.module('badgeDefs', [
])

    .factory("BadgeDefs", function($http){

      var data = {}

      function load(){

        var url = "/api/badges"
        return $http.get(url).success(function(resp){

          // clear the data object
          for (var member in data) delete data[member];

          // put the response in the data object
          _.each(resp, function(v, k){
            data[k] = v
          })

        })
      }

      return {
        d: data,
        load: load
      }
    })
angular.module("numFormat", [])

    .factory("NumFormat", function($location){

        var commas = function(x) { // from stackoverflow
            if (!x) {
                return x
            }
            var parts = x.toString().split(".");
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            return parts.join(".");
        }

        var short = function(num, fixedAt){
            if (typeof num === "string"){
                return num  // not really a number
            }

            // from http://stackoverflow.com/a/14994860/226013
            if (num === null){
                return 0
            }
            if (num === 0){
                return 0
            }

            if (num >= 1000000) {
                return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
            }
            if (num >= 100000) { // no decimal if greater than 100thou
                return (num / 1000).toFixed(0).replace(/\.0$/, '') + 'k';
            }

            if (num >= 1000) {
                return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
            }


            //if (num < 1) {
            //    return Math.round(num * 100) / 100
            //}

            return Math.floor(num);
        }

        var round = function(num){
            return Math.round(num)
        }

        var doubleUrlEncode = function(str){
            return encodeURIComponent( encodeURIComponent(str) )
        }

        // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
        var ordinal = function(n) {
            n = Math.round(n)
            var s=["th","st","nd","rd"],
                v=n%100;
            return n+(s[(v-20)%10]||s[v]||s[0]);
        }

        return {
            short: short,
            commas: commas,
            round: round,
            ordinal: ordinal,
            doubleUrlEncode: doubleUrlEncode

        }
    });
angular.module('pageService', [
  ])



  .factory("PageService", function(){

    var data = {}
    var defaultData = {}

    function reset(){
      console.log("resetting the page service data")
      _.each(defaultData, function(v, k){
        data[k] = v
      })
    }

    return {
      d: data,
      reset: reset
    }


  })
angular.module('person', [
])



    .factory("Person", function($http){

      var data = {}

      function load(orcidId){
        var url = "/api/person/" + orcidId
        console.log("getting person with orcid id ", orcidId)
        return $http.get(url).success(function(resp){

          // clear the data object
          for (var member in data) delete data[member];

          // put the response in the data object
          _.each(resp, function(v, k){
            data[k] = v
          })
        })
      }

      function getBadgesWithConfigs(configDict) {
        var ret = []
        _.each(data.badges, function(myBadge){
          var badgeDef = configDict[myBadge.name]
          var enrichedBadge = _.extend(myBadge, badgeDef)
          ret.push(enrichedBadge)
        })

        return ret
      }

      return {
        d: data,
        load: load,
        getBadgesWithConfigs: getBadgesWithConfigs
      }
    })
angular.module('profileService', [
  ])



  .factory("ProfileService", function($http,
                                      $timeout,
                                      $location){

    var data = {
      profile: {
        articles:[]
      }
    }

    function profileStillLoading(){
      console.log("testing if profile still loading", data.profile.articles)
      return _.any(data.profile.articles, function(article){
        return _.isNull(article.percentile)
      })
    }

    function getProfile(slug){
      var url = "/profile/" + slug
      console.log("getting profile for", slug)
      return $http.get(url).success(function(resp){
        data.profile = resp

        if (profileStillLoading()){
          $timeout(function(){
            getProfile(slug)
          }, 1000)
        }

      })
    }

    return {
      data: data,
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids, coreJournals) {
        console.log("i am making a profile:", name, pmids)
        var postData = {
          name: name,
          pmids: pmids,
          core_journals: coreJournals
        }
        $http.post("/profile",postData)
          .success(function(resp, status, headers){
            console.log("yay got a resp from /profile!", resp)
            $location.path("/u/" + resp.slug)
          })
      },

      getProfile: getProfile
    }


  })
angular.module('settingsPage', [
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/me/settings', {
            templateUrl: 'settings-page/settings-page.tpl.html',
            controller: 'settingsPageCtrl',
            resolve: {
                isAuth: function($q, $auth){
                    if ($auth.isAuthenticated()){
                        return $q.resolve()
                    }
                    else {
                        return $q.reject("/settings only works if you're logged in.")
                    }
                }
            }
        })
    })



    .controller("settingsPageCtrl", function($scope, $auth, $location, $http){

        console.log("the settings page loaded")
        $scope.wantToDelete = false
        $scope.deleteProfile = function() {
            $http.delete("/api/me")
                .success(function(resp){
                    $auth.logout()
                    $location.path("/")
                    alert("Your profile has been deleted.")
                })
                .error(function(){
                    alert("Sorry, something went wrong!")
                })
        }


        $scope.syncState = 'ready'

        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.syncState = "working"
            $http.post("/api/me", {action: "pull_from_orcid"})
                .success(function(resp){
                    console.log("we updated you successfully!")
                    $scope.syncState = "success"
                })
        }

    })













angular.module('snippet', [
  ])



  .controller("packageSnippetCtrl", function($scope){

      //if ($scope.dep) {
      //  $scope.snippetPackage = $scope.dep
      //}
      //
      //else if ($scope.package) {
      //  //$scope.snippetPackage = $scope.package
      //}


//    var subscoreNames = [
//      "num_downloads",
//      "pagerank",
//      "num_citations"
//    ]
//    var subscores = _.map(subscoreNames, function(name){
//      return {
//        name: name,
//        percentile: $scope.package[name + "_percentile"],
//        val: $scope.package[name]
//      }
//    })

//    var subScoresSum =  _.reduce(
//      _.map(subScores, function(x){return x[1]}),
//      function(memo, num){ return memo + num; },
//      0
//    )
//    $scope.subScores = subscores
  })


  .controller("personSnippetCtrl", function($scope){

  })


angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginPageCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http) {

    })


    .controller("LoginPageCtrl", function ($scope, $sce, $http) {
        console.log("login page controller is running!")

    })

    .controller("LandingPageCtrl", function ($scope, $rootScope, $http, $auth, $location) {
        console.log("landing page!", $scope.global)
        $scope.global.isLandingPage = true


        $scope.authenticate = function () {
            console.log("authenticate!")

            $auth.authenticate("orcid")
                .then(function(resp){
                    var orcid_id = $auth.getPayload()['sub']
                    console.log("you have successfully logged in!", resp, $auth.getPayload())

                    // take the user to their profile.
                    $location.path("/u/" + orcid_id)

                })
                .catch(function(error){
                    console.log("there was an error logging in:", error)
                })
        };



    })











angular.module('templates.app', ['badge-page/badge-page.tpl.html', 'footer/footer.tpl.html', 'header/header.tpl.html', 'header/search-result.tpl.html', 'package-page/package-page.tpl.html', 'person-page/person-page.tpl.html', 'settings-page/settings-page.tpl.html', 'snippet/package-impact-popover.tpl.html', 'snippet/package-snippet.tpl.html', 'snippet/person-impact-popover.tpl.html', 'snippet/person-mini.tpl.html', 'snippet/person-snippet.tpl.html', 'snippet/tag-snippet.tpl.html', 'static-pages/about.tpl.html', 'static-pages/landing.tpl.html', 'static-pages/login.tpl.html']);

angular.module("badge-page/badge-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("badge-page/badge-page.tpl.html",
    "<div class=\"page badge-page\">\n" +
    "    <a href=\"/u/{{ person.orcid_id }}\" class=\"back-to-profile\">\n" +
    "        <i class=\"fa fa-chevron-left\"></i>\n" +
    "        Back to {{ person.given_names }}'s profile\n" +
    "\n" +
    "    </a>\n" +
    "\n" +
    "    <h2>\n" +
    "        <i class=\"fa fa-circle badge-level-{{ badge.level }}\"></i>\n" +
    "        <span class=\"name\">\n" +
    "            {{ badge.display_name }}\n" +
    "        </span>\n" +
    "    </h2>\n" +
    "    <div class=\"who-earned-it\">\n" +
    "        {{ person.given_names }} earned this badge\n" +
    "        <span class=\"earned-time\">\n" +
    "         {{ moment(badge.created).fromNow() }}\n" +
    "        </span>\n" +
    "    </div>\n" +
    "    <div class=\"various-descriptions\">\n" +
    "        <div class=\"description\">\n" +
    "            {{ badge.description }}\n" +
    "        </div>\n" +
    "        <div class=\"extra-description\" ng-show=\"badge.extra_description\">\n" +
    "            {{ badge.extra_description }}\n" +
    "        </div>\n" +
    "        <div class=\"level-description\">\n" +
    "            <span class=\"gold\" ng-show=\"badge.level=='gold'\">\n" +
    "                This is a <span class=\"level badge-level-gold\">gold-level badge.</span>\n" +
    "                That's impressive, gold badges are rarely awarded!\n" +
    "            </span>\n" +
    "            <span class=\"silver\" ng-show=\"badge.level=='silver'\">\n" +
    "                This is a <span class=\"level badge-level-silver\">silver-level badge.</span>\n" +
    "                That's pretty good, Silver badges are not easy to get!\n" +
    "            </span>\n" +
    "            <span class=\"gold\" ng-show=\"badge.level=='bronze'\">\n" +
    "                This is a <span class=\"level badge-level-bronze\">bronze-level badge.</span>\n" +
    "                They are relatively easy to get but nothing to sneeze at!\n" +
    "            </span>\n" +
    "\n" +
    "            <span class=\"learn-more\">\n" +
    "                You can learn more about badges on our <a href=\"/about/badges\">About Badges page.</a>\n" +
    "            </span>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"products\" ng-show=\"badge.dois.length\">\n" +
    "        <h3>{{ person.given_names }} earned this badge based on\n" +
    "            {{ badge.dois.length }} product<span ng-show=\"badge.dois.length > 1\">s</span>:</h3>\n" +
    "        <table>\n" +
    "            <thead>\n" +
    "                <th class=\"biblio\"></th>\n" +
    "                <th class=\"sources\"></th>\n" +
    "                <tn class=\"score\"></tn>\n" +
    "                <tn class=\"has-new\"></tn>\n" +
    "            </thead>\n" +
    "            <tbody>\n" +
    "                <tr ng-repeat=\"product in badgeProducts | orderBy : '-altmetric_score'\">\n" +
    "                    <td class=\"biblio\">\n" +
    "                        <div class=\"title\">\n" +
    "                            {{ product.title }}\n" +
    "                        </div>\n" +
    "                        <div class=\"more\">\n" +
    "                            <span class=\"year\">{{ product.year }}</span>\n" +
    "                            <span class=\"journal\">{{ product.journal }}</span>\n" +
    "                        </div>\n" +
    "                    </td>\n" +
    "                    <td class=\"sources has-oodles-{{ product.sources.length > 6 }}\">\n" +
    "                        <span class=\"source-icon\"\n" +
    "                              tooltip=\"a million wonderful things\"\n" +
    "                              ng-repeat=\"source in product.sources | orderBy: 'posts_count'\">\n" +
    "                            <img src=\"/static/img/favicons/{{ source.source_name }}.ico\">\n" +
    "                        </span>\n" +
    "                    </td>\n" +
    "                    <td class=\"score\">\n" +
    "                        {{ numFormat.short(product.altmetric_score) }}\n" +
    "                    </td>\n" +
    "                    <td class=\"has-new\">\n" +
    "                        <i class=\"fa fa-arrow-up\" ng-show=\"product.events_last_week_count > 0\"></i>\n" +
    "                    </td>\n" +
    "\n" +
    "                </tr>\n" +
    "            </tbody>\n" +
    "\n" +
    "        </table>\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "</div>");
}]);

angular.module("footer/footer.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("footer/footer.tpl.html",
    "<div id=\"footer\" ng-controller=\"footerCtrl\">\n" +
    "\n" +
    "\n" +
    "\n" +
    "    <div class=\"links\">\n" +
    "        <a href=\"/about\">\n" +
    "            <i class=\"fa fa-info-circle\"></i>\n" +
    "            About\n" +
    "        </a>\n" +
    "        <a href=\"https://github.com/Impactstory/depsy\">\n" +
    "            <i class=\"fa fa-github\"></i>\n" +
    "            Source code\n" +
    "        </a>\n" +
    "        <a href=\"https://twitter.com/depsy_org\">\n" +
    "            <i class=\"fa fa-twitter\"></i>\n" +
    "            Twitter\n" +
    "        </a>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "    <div id=\"mc_embed_signup\">\n" +
    "        <form action=\"//impactstory.us4.list-manage.com/subscribe/post?u=26fcc4e14b24319755845d9e0&amp;id=c9dd1339cd\" method=\"post\" id=\"mc-embedded-subscribe-form\" name=\"mc-embedded-subscribe-form\" class=\"validate\" target=\"_blank\" novalidate>\n" +
    "\n" +
    "            <div id=\"mc_embed_signup_scroll\" class=\"input-group\">\n" +
    "                <input class=\"form-control text-input\" type=\"email\" value=\"\" name=\"EMAIL\" class=\"email\" id=\"mce-EMAIL\" placeholder=\"Join the mailing list\" required>\n" +
    "           <span class=\"input-group-btn\">\n" +
    "              <input class=\"btn btn-default\" type=\"submit\" value=\"Go\" name=\"subscribe\" id=\"mc-embedded-subscribe\" class=\"button\">\n" +
    "           </span>\n" +
    "\n" +
    "                <!-- real people should not fill this in and expect good things - do not remove this or risk form bot signups-->\n" +
    "                <div style=\"position: absolute; left: -5000px;\"><input type=\"text\" name=\"b_26fcc4e14b24319755845d9e0_c9dd1339cd\" tabindex=\"-1\" value=\"\"></div>\n" +
    "            </div>\n" +
    "        </form>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"built-by\">\n" +
    "        Built with <i class=\"fa fa-heart\"></i> at <a href=\"http://impactstory.org/about\">Impactstory</a>,\n" +
    "        <br>\n" +
    "        with support from the National Science Foundation\n" +
    "    </div>\n" +
    "\n" +
    "</div>");
}]);

angular.module("header/header.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("header/header.tpl.html",
    "<div class=\"ti-header\" ng-controller=\"headerCtrl\">\n" +
    "   <h1>\n" +
    "      <a href=\"/\">\n" +
    "         <img src=\"static/img/logo-circle.png\" alt=\"\"/>\n" +
    "      </a>\n" +
    "   </h1>\n" +
    "\n" +
    "   <div class=\"ti-menu\">\n" +
    "      <a href=\"leaderboard?type=people\"\n" +
    "         popover=\"Top authors\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover-placement=\"bottom\"\n" +
    "         class=\"menu-link\" id=\"leaders-menu-link\">\n" +
    "         <i class=\"fa fa-user\"></i>\n" +
    "      </a>\n" +
    "      <a href=\"leaderboard?type=packages\"\n" +
    "         popover=\"Top projects\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover-placement=\"bottom\"\n" +
    "         class=\"menu-link\" id=\"leaders-menu-link\">\n" +
    "         <i class=\"fa fa-archive\"></i>\n" +
    "      </a>\n" +
    "      <a href=\"leaderboard?type=tags\"\n" +
    "         popover=\"Top topics\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover-placement=\"bottom\"\n" +
    "         class=\"menu-link\" id=\"leaders-menu-link\">\n" +
    "         <i class=\"fa fa-tag\"></i>\n" +
    "      </a>\n" +
    "\n" +
    "      <!-- needs weird style hacks -->\n" +
    "      <a href=\"about\"\n" +
    "         class=\"menu-link about\" id=\"leaders-menu-link\">\n" +
    "         <i\n" +
    "         popover=\"Learn more about Depsy\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover-placement=\"bottom\" class=\"fa fa-question-circle\"></i>\n" +
    "      </a>\n" +
    "\n" +
    "\n" +
    "   </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "   <div class=\"search-box\">\n" +
    "    <input type=\"text\"\n" +
    "           id=\"search-box\"\n" +
    "           ng-model=\"searchResultSelected\"\n" +
    "           placeholder=\"Search packages, authors, and topics\"\n" +
    "           typeahead=\"result as result.name for result in doSearch($viewValue)\"\n" +
    "           typeahead-loading=\"loadingLocations\"\n" +
    "           typeahead-no-results=\"noResults\"\n" +
    "           typeahead-template-url=\"header/search-result.tpl.html\"\n" +
    "           typeahead-focus-first=\"false\"\n" +
    "           typeahead-on-select=\"onSelect($item)\"\n" +
    "           class=\"form-control input-lg\">\n" +
    "   </div>\n" +
    "\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("header/search-result.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("header/search-result.tpl.html",
    "\n" +
    "<div class=\"typeahead-group-header\" ng-if=\"match.model.is_first\">\n" +
    "   <span class=\"group-header-type pypy-package\" ng-if=\"match.model.type=='pypi_project'\">\n" +
    "      <img src=\"static/img/python.png\" alt=\"\"/>\n" +
    "      Python packages <span class=\"where\">on <a href=\"https://pypi.python.org/pypi\">PyPI</a></span>\n" +
    "   </span>\n" +
    "   <span class=\"group-header-type cran-package\" ng-if=\"match.model.type=='cran_project'\">\n" +
    "      <img src=\"static/img/r-logo.png\" alt=\"\"/>\n" +
    "      R packages <span class=\"where\">on <a href=\"https://cran.r-project.org/\">CRAN</a></span>\n" +
    "   </span>\n" +
    "   <span class=\"group-header-type people\" ng-if=\"match.model.type=='person'\">\n" +
    "      <i class=\"fa fa-user\"></i>\n" +
    "      People\n" +
    "   </span>\n" +
    "   <span class=\"group-header-type tags\" ng-if=\"match.model.type=='tag'\">\n" +
    "      <i class=\"fa fa-tag\"></i>\n" +
    "      Tags\n" +
    "   </span>\n" +
    "\n" +
    "</div>\n" +
    "<a ng-href=\"package/python/{{ match.model.name }}\" ng-if=\"match.model.type=='pypi_project'\">\n" +
    "   <span class=\"name\">\n" +
    "      {{ match.model.name }}\n" +
    "   </span>\n" +
    "   <span  class=\"summary\">\n" +
    "      {{ match.model.summary }}\n" +
    "   </span>\n" +
    "</a>\n" +
    "<a ng-href=\"package/r/{{ match.model.name }}\" ng-if=\"match.model.type=='cran_project'\">\n" +
    "   <span class=\"name\">\n" +
    "      {{ match.model.name }}\n" +
    "   </span>\n" +
    "   <span  class=\"summary\">\n" +
    "      {{ match.model.summary }}\n" +
    "   </span>\n" +
    "</a>\n" +
    "<a ng-href=\"person/{{ match.model.id }}\" ng-if=\"match.model.type=='person'\">\n" +
    "   <span class=\"name\">\n" +
    "      {{ match.model.name }}\n" +
    "   </span>\n" +
    "</a>\n" +
    "<a ng-href=\"tag/{{ match.model.urlName }}\" ng-if=\"match.model.type=='tag'\">\n" +
    "   <span class=\"name\">\n" +
    "      {{ match.model.name }}\n" +
    "   </span>\n" +
    "   <span class=\"tag summary\">\n" +
    "      {{ match.model.impact }} packages\n" +
    "   </span>\n" +
    "</a>\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("package-page/package-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("package-page/package-page.tpl.html",
    "<div class=\"page entity-page package-page\">\n" +
    "\n" +
    "\n" +
    "    <div class=\"ti-page-sidebar\">\n" +
    "        <div class=\"sidebar-header\">\n" +
    "\n" +
    "            <div class=\"about\">\n" +
    "                <div class=\"meta\">\n" +
    "               <span class=\"name\">\n" +
    "                  {{ package.name }}\n" +
    "                   <i popover-title=\"Research software\"\n" +
    "                      popover-trigger=\"mouseenter\"\n" +
    "                      popover=\"We decide if something is research software based on language, as well as words in project tags, titles, and summaries.\"\n" +
    "                      ng-show=\"package.is_academic\"\n" +
    "                      class=\"is-academic fa fa-graduation-cap\"></i>\n" +
    "               </span>\n" +
    "\n" +
    "                    <div class=\"summary\">\n" +
    "                        {{ package.summary }}\n" +
    "                    </div>\n" +
    "                </div>\n" +
    "                <div class=\"links\">\n" +
    "                    <a class=\"language-icon r\"\n" +
    "                       href=\"https://cran.r-project.org/web/packages/{{ package.name }}/index.html\"\n" +
    "                       ng-if=\"package.language=='r'\">\n" +
    "                        R\n" +
    "                    </a>\n" +
    "                    <a class=\"language-icon python\"\n" +
    "                       href=\"https://pypi.python.org/pypi/{{ package.name }}\"\n" +
    "                       ng-if=\"package.language=='python'\">\n" +
    "                        py\n" +
    "                    </a>\n" +
    "                    <a class=\"github\"\n" +
    "                       ng-show=\"package.github_repo_name\"\n" +
    "                       href=\"http://github.com/{{ package.github_owner }}/{{ package.github_repo_name }}\">\n" +
    "                        <i class=\"fa fa-github\"></i>\n" +
    "                    </a>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "        <div class=\"sidebar-section tags\" ng-if=\"package.tags.length\">\n" +
    "            <h3>Tags</h3>\n" +
    "            <div class=\"tags\">\n" +
    "                <a class=\"tag\"\n" +
    "                   href=\"tag/{{ format.doubleUrlEncode(tag) }}\"\n" +
    "                   ng-repeat=\"tag in package.tags\">\n" +
    "                    {{ tag }}\n" +
    "                </a>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "        <div class=\"sidebar-section top-contribs\">\n" +
    "            <h3>{{ package.all_contribs.length }} contributors</h3>\n" +
    "            <div class=\"contrib\"\n" +
    "                 ng-repeat=\"person_package in package.top_contribs | orderBy: '-credit'\">\n" +
    "                <wheel popover-right=\"true\"></wheel>\n" +
    "\n" +
    "                  <div class=\"vis impact-stick\">\n" +
    "                      <div class=\"none\" ng-show=\"person_package.subscores.length == 0\">\n" +
    "                          none\n" +
    "                      </div>\n" +
    "                     <div class=\"bar-inner {{ subscore.name }}\"\n" +
    "                          style=\"width: {{ subscore.percentile * 33.33333 }}%;\"\n" +
    "                          ng-repeat=\"subscore in person_package.subscores\">\n" +
    "                     </div>\n" +
    "                  </div>\n" +
    "\n" +
    "                <!--\n" +
    "                <img class=\"person-icon\" src=\"{{ person_package.icon_small }}\" alt=\"\"/>\n" +
    "                -->\n" +
    "\n" +
    "                <a class=\"name\" href=\"person/{{ person_package.id }}\">{{ person_package.name }}</a>\n" +
    "            </div>\n" +
    "\n" +
    "            <span class=\"plus-more btn btn-default btn-xs\"\n" +
    "                  ng-show=\"package.all_contribs.length > package.top_contribs.length\"\n" +
    "                  ng-click=\"apiOnly()\">\n" +
    "                <i class=\"fa fa-plus\"></i>\n" +
    "                <span class=\"val\">{{ package.all_contribs.length - package.top_contribs.length }}</span> more\n" +
    "            </span>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "        <div class=\"sidebar-section actions\">\n" +
    "            <a class=\"json-link btn btn-default\"\n" +
    "               target=\"_self\"\n" +
    "               href=\"api/package/{{ package.host }}/{{ package.name }}\">\n" +
    "                <i class=\"fa fa-cogs\"></i>\n" +
    "                View in API\n" +
    "            </a>\n" +
    "\n" +
    "            <badge entity=\"package/{{ package.host }}/{{ package.name }}\"></badge>\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <!--\n" +
    "         <a href=\"https://twitter.com/share?url={{ encodeURIComponent('http://google.com') }}\" >Tweet</a>\n" +
    "         -->\n" +
    "\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "    <div class=\"ti-page-body\">\n" +
    "\n" +
    "\n" +
    "        <div class=\"subscore package-page-subscore overall is-academic-{{ package.is_academic }}\">\n" +
    "            <div class=\"body research-package\">\n" +
    "                <div class=\"metrics\">\n" +
    "                    <span class=\"package-percentile\">\n" +
    "                        {{ format.round(package.impact_percentile * 100) }}\n" +
    "                    </span>\n" +
    "                    <span class=\"ti-label\">\n" +
    "                        percentile impact overall\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "                <div class=\"explanation\">\n" +
    "                    Compared to all research software on\n" +
    "                    <span class=\"repo cran\" ng-show=\"package.host=='cran'\">CRAN</span>\n" +
    "                    <span class=\"repo PyPi\" ng-show=\"package.host=='pypi'\">PyPI</span>,\n" +
    "                    based on relative\n" +
    "                    <span class=\"num_downloads\">downloads,</span>\n" +
    "                    <span class=\"pagerank\">software reuse,</span> and\n" +
    "                    <span class=\"num_mentions\">citation.</span>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"body non-research-package\">\n" +
    "                <div class=\"heading\">\n" +
    "                    Not research software\n" +
    "                </div>\n" +
    "                <div class=\"explanation\">\n" +
    "                    Based on name, tags, and description, we're guessing this isn't\n" +
    "                    research software—so we haven't calculated impact percentile information. <br>\n" +
    "                    <a class=\"btn btn-default btn-xs\" href=\"https://github.com/Impactstory/depsy/issues\">did we guess wrong?</a>\n" +
    "                </div>\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"subscore package-page-subscore {{ subscore.name }}\"\n" +
    "             ng-repeat=\"subscore in package.subscores\">\n" +
    "            <h3>\n" +
    "                <i class=\"fa {{ subscore.icon }}\"></i>\n" +
    "                {{ subscore.display_name }}\n" +
    "            </h3>\n" +
    "            <div class=\"body\">\n" +
    "                <div class=\"metrics\">\n" +
    "                    <div class=\"impact-stick vis\" ng-show=\"package.is_academic\">\n" +
    "                        <div class=\"bar-inner {{ subscore.name }}\" style=\"width: {{ subscore.percentile * 100 }}%\">\n" +
    "                        </div>\n" +
    "\n" +
    "                    </div>\n" +
    "                    <span class=\"main-metric\" ng-show=\"subscore.name=='pagerank'\">\n" +
    "                        {{ format.short(subscore.val, 2) }}\n" +
    "                    </span>\n" +
    "                    <span class=\"main-metric\" ng-show=\"subscore.name != 'pagerank'\">\n" +
    "                        {{ format.short(subscore.val) }}\n" +
    "                    </span>\n" +
    "                    <span class=\"percentile\" ng-show=\"package.is_academic\">\n" +
    "                        <span class=\"val\">\n" +
    "                            {{ format.round(subscore.percentile * 100) }}\n" +
    "                        </span>\n" +
    "                        <span class=\"descr\">\n" +
    "                            percentile\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "\n" +
    "                <div class=\"explanation\">\n" +
    "                    <div class=\"citations-explanation\" ng-show=\"subscore.name=='num_mentions'\">\n" +
    "                        <p>\n" +
    "                            Based on term searches in <br>\n" +
    "                                <span class=\"citation-link\" ng-repeat=\"link in package.citations_dict\">\n" +
    "                                    <a href=\"{{ link.url }}\">{{ link.display_name }} ({{ link.count }})</a>\n" +
    "                                    <span class=\"and\" ng-show=\"!$last\">and</span>\n" +
    "                                </span>\n" +
    "                        </p>\n" +
    "                        <p>\n" +
    "                            <a href=\"https://github.com/Impactstory/depsy-research/blob/master/introducing_depsy.md#literature-reuse\">\n" +
    "                                Read more about how we got this number.\n" +
    "                            </a>\n" +
    "                        </p>\n" +
    "                    </div>\n" +
    "                    <div class=\"downloads-explanation\" ng-show=\"subscore.name=='num_downloads'\">\n" +
    "                        Based on latest monthly downloads stats from\n" +
    "                        <span class=\"repo cran\" ng-show=\"package.host=='cran'\">CRAN.</span>\n" +
    "                        <span class=\"repo PyPi\" ng-show=\"package.host=='pypi'\">PyPI.</span>\n" +
    "                    </div>\n" +
    "                    <div class=\"pagerank-explanation\" ng-show=\"subscore.name=='pagerank'\">\n" +
    "                        <p>\n" +
    "                            Measures how often this package is imported by\n" +
    "\n" +
    "                            <span class=\"repo cran\" ng-show=\"package.host=='cran'\">CRAN</span>\n" +
    "                            <span class=\"repo PyPi\" ng-show=\"package.host=='pypi'\">PyPI</span>\n" +
    "                            and GitHub projects, based on its PageRank in the dependency network.\n" +
    "\n" +
    "                        </p>\n" +
    "                        <p>\n" +
    "                            <a href=\"https://github.com/Impactstory/depsy-research/blob/master/introducing_depsy.md#software-reuse\">\n" +
    "                                Read more about what this number means.\n" +
    "                            </a>\n" +
    "                        </p>\n" +
    "\n" +
    "\n" +
    "                    </div>\n" +
    "                </div>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <!-- Top Importers. This is just for the pagerank subscore -->\n" +
    "            <div class=\"top-importers\" ng-show=\"subscore.name=='pagerank' && package.indegree\">\n" +
    "                <h4>\n" +
    "                    <i class=\"fa fa-recycle\"></i>\n" +
    "                    Reused by <span class=\"details\">{{ package.indegree }} projects</span>\n" +
    "                </h4>\n" +
    "\n" +
    "                <div class=\"dep-container\"\n" +
    "                     ng-repeat=\"dep in package.top_neighbors | orderBy: ['-is_github', '-impact']\">\n" +
    "\n" +
    "\n" +
    "                    <!-- CRAN or PyPI package -->\n" +
    "                    <div class=\"package dep\" ng-if=\"dep.host\">\n" +
    "                        <div class=\"top-line\">\n" +
    "\n" +
    "                            <div class=\"left-metrics is-academic\" ng-show=\"dep.is_academic\">\n" +
    "                                <div class=\"vis impact-stick is-academic-{{ dep.is_academic }}\">\n" +
    "                                    <div ng-repeat=\"subscore in dep.subscores\"\n" +
    "                                         class=\"bar-inner {{ subscore.name }}\"\n" +
    "                                         style=\"width: {{ subscore.percentile * 33.333 }}%;\">\n" +
    "                                    </div>\n" +
    "                                </div>\n" +
    "                            </div>\n" +
    "\n" +
    "\n" +
    "                            <span class=\"left-metrics not-academic\"\n" +
    "                                  ng-show=\"!dep.is_academic\"\n" +
    "                                  popover=\"Based on name, tags, and description, we're guessing this isn't research software—so we haven't collected detailed impact info.\"\n" +
    "                                  popover-trigger=\"mouseenter\">\n" +
    "                                <span class=\"non-research\">\n" +
    "                                    non- research\n" +
    "                                </span>\n" +
    "\n" +
    "                            </span>\n" +
    "\n" +
    "\n" +
    "                            <a class=\"name\" href=\"package/{{ dep.language }}/{{ dep.name }}\">\n" +
    "                                {{ dep.name }}\n" +
    "                            </a>\n" +
    "\n" +
    "                            <i popover-title=\"Research software\"\n" +
    "                               popover-trigger=\"mouseenter\"\n" +
    "                               popover=\"We decide projects are research software based on their names, tags, and summaries.\"\n" +
    "                               ng-show=\"dep.is_academic\"\n" +
    "                               class=\"is-academic fa fa-graduation-cap\"></i>\n" +
    "                        </div>\n" +
    "                        <div class=\"underline\">\n" +
    "                            {{ dep.summary }}\n" +
    "                        </div>\n" +
    "                    </div>\n" +
    "\n" +
    "                    <!-- GitHub repo -->\n" +
    "                    <div class=\"github dep\" ng-if=\"!dep.host\">\n" +
    "                        <div class=\"top-line\">\n" +
    "                            <div class=\"vis\"\n" +
    "                                 popover-trigger=\"mouseenter\"\n" +
    "                                 popover=\"{{ dep.stars }} GitHub stars\">\n" +
    "                                {{ dep.stars }}\n" +
    "                                <i class=\"fa fa-star\"></i>\n" +
    "                            </div>\n" +
    "\n" +
    "                            <span class=\"name\">\n" +
    "                                <a href=\"http://github.com/{{ dep.login }}/{{ dep.repo_name }}\"\n" +
    "                                   popover-trigger=\"mouseenter\"\n" +
    "                                   popover=\"Depsy only indexes packages distributed via CRAN or PyPI, but you can view this project on GitHub.\"\n" +
    "                                   class=\"github-link\">\n" +
    "                                    <i class=\"fa fa-github\"></i>\n" +
    "                                    {{ dep.repo_name }}\n" +
    "                                </a>\n" +
    "                            </span>\n" +
    "                        </div>\n" +
    "                        <div class=\"underline\">\n" +
    "                            {{ dep.summary }}\n" +
    "                        </div>\n" +
    "                    </div>\n" +
    "                </div> <!-- end this dep -->\n" +
    "\n" +
    "                <span class=\"plus-more btn btn-default btn-xs\"\n" +
    "                      ng-show=\"package.indegree > package.top_neighbors.length\"\n" +
    "                      ng-click=\"apiOnly()\">\n" +
    "                    <i class=\"fa fa-plus\"></i>\n" +
    "                    <span class=\"val\">{{ package.indegree - package.top_neighbors.length }}</span> more\n" +
    "                </span>\n" +
    "\n" +
    "            </div> <!-- end of the dep list widget -->\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "");
}]);

angular.module("person-page/person-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("person-page/person-page.tpl.html",
    "<div class=\"page person\">\n" +
    "\n" +
    "\n" +
    "\n" +
    "    <div class=\"person-header row\">\n" +
    "        <img class=\"avatar\" ng-src=\"{{ person.picture }}\" alt=\"\"/>\n" +
    "\n" +
    "        <div class=\"bio\">\n" +
    "            <h2 class=\"name\">\n" +
    "               {{ person.given_names }} {{ person.family_name }}\n" +
    "            </h2>\n" +
    "            <div class=\"aff\">\n" +
    "                <span class=\"institution\">{{ person.affiliation_name }}</span>\n" +
    "                <span class=\"role\">\n" +
    "                    {{ person.affiliation_role_title }}\n" +
    "                </span>\n" +
    "            </div>\n" +
    "            <div class=\"accounts\">\n" +
    "                <a href=\"http://twitter.com/{{ person.twitter }}\"\n" +
    "                   ng-show=\"person.twitter\"\n" +
    "                   class=\"twitter\">\n" +
    "                    <i class=\"fa fa-twitter\"></i>\n" +
    "                    Twitter\n" +
    "                </a>\n" +
    "                <a href=\"http://depsy.org/{{ person.depsy }}\"\n" +
    "                        ng-show=\"person.depsy\">\n" +
    "                    Depsy\n" +
    "                </a>\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"person-main row\">\n" +
    "        <div class=\"scores-col col-md-4\">\n" +
    "            <div class=\"main-score {{ person.belt }}belt\">\n" +
    "                <span class=\"score-value\">\n" +
    "                    {{ numFormat.short(person.altmetric_score) }}\n" +
    "                </span>\n" +
    "                <span class=\"score-label\">\n" +
    "                    online impact\n" +
    "                </span>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"score-belt {{ person.belt }}belt\">\n" +
    "                {{ person.belt }} belt\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"sources-list\">\n" +
    "                <div class=\"source\" ng-repeat=\"source in person.sources | orderBy: '-posts_count'\">\n" +
    "                    <span class=\"favicon\">\n" +
    "                        <img ng-src=\"/static/img/favicons/{{ source.source_name }}.ico\">\n" +
    "                    </span>\n" +
    "                    <span class=\"name\">{{ source.display_name }}</span>\n" +
    "                    <span class=\"last-week\">\n" +
    "                        <span class=\"show\"\n" +
    "                              tooltip=\"{{ source.events_last_week_count }} new this week\"\n" +
    "                              ng-show=\"source.events_last_week_count\">\n" +
    "                            <i class=\"fa fa-arrow-up\"></i>\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "                    <span class=\"value\">\n" +
    "                        {{ numFormat.short(source.posts_count) }}\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "        <div class=\"main-col col-md-8\">\n" +
    "            <!--\n" +
    "            <h3>\n" +
    "                <span class=\"count\">{{ person.badges.length }} </span>\n" +
    "                <span class=\"name\">\n" +
    "                    badges\n" +
    "                </span>\n" +
    "            </h3>\n" +
    "            -->\n" +
    "            <div class=\"badges row\">\n" +
    "                <div class=\"badge-col col col-md-4 badge-level-{{ badgeCol.level }}\"\n" +
    "                     ng-repeat=\"badgeCol in badgeCols\">\n" +
    "                    <h4 class=\"badge-level-{{ badgeCol.level }}\">\n" +
    "                        <span class=\"count\">{{ badgeCol.list.length }}</span>\n" +
    "                        <span class=\"name\">\n" +
    "                            {{ badgeCol.level}} badge<span ng-hide=\"badgeCol.list.length==1\">s</span>\n" +
    "                        </span>\n" +
    "                    </h4>\n" +
    "                    <div class=\"badges-list\">\n" +
    "                        <a class=\"ti-badge badge-level-{{ badge.level }}\"\n" +
    "                           href=\"/u/{{ person.orcid_id }}/badge/{{ badge.name }}\"\n" +
    "                            ng-repeat=\"badge in badgeCol.list\">\n" +
    "                            <i class=\"fa fa-circle badge-level-{{ badge.level }}\"></i>\n" +
    "                            <span class=\"name\">\n" +
    "                                {{ badge.display_name }}\n" +
    "                            </span>\n" +
    "                            <div class=\"count\" ng-show=\"badge.dois.length\">\n" +
    "                                &times;{{ badge.dois.length }}\n" +
    "                            </div>\n" +
    "\n" +
    "                        </a>\n" +
    "                    </div>\n" +
    "\n" +
    "                </div>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "            <h3 class=\"products-heading\">\n" +
    "                <span class=\"count\">{{ person.products.length }}</span>\n" +
    "                <span class=\"name\">research products</span>\n" +
    "            </h3>\n" +
    "            <div class=\"products row\">\n" +
    "                <table>\n" +
    "                    <thead>\n" +
    "                        <th class=\"biblio\"></th>\n" +
    "                        <th class=\"sources\"></th>\n" +
    "                        <tn class=\"score\"></tn>\n" +
    "                        <tn class=\"has-new\"></tn>\n" +
    "                    </thead>\n" +
    "                    <tbody>\n" +
    "                        <tr ng-repeat=\"product in person.products | orderBy : '-altmetric_score'\">\n" +
    "                            <td class=\"biblio\">\n" +
    "                                <div class=\"title\">\n" +
    "                                    {{ product.title }}\n" +
    "                                </div>\n" +
    "                                <div class=\"more\">\n" +
    "                                    <span class=\"year\">{{ product.year }}</span>\n" +
    "                                    <span class=\"journal\">{{ product.journal }}</span>\n" +
    "                                </div>\n" +
    "                            </td>\n" +
    "                            <td class=\"sources has-oodles-{{ product.sources.length > 6 }}\">\n" +
    "                                <span class=\"source-icon\"\n" +
    "                                      tooltip=\"a million wonderful things\"\n" +
    "                                      ng-repeat=\"source in product.sources | orderBy: 'posts_count'\">\n" +
    "                                    <img src=\"/static/img/favicons/{{ source.source_name }}.ico\">\n" +
    "                                </span>\n" +
    "                            </td>\n" +
    "                            <td class=\"score\">\n" +
    "                                {{ numFormat.short(product.altmetric_score) }}\n" +
    "                            </td>\n" +
    "                            <td class=\"has-new\">\n" +
    "                                <i class=\"fa fa-arrow-up\" ng-show=\"product.events_last_week_count > 0\"></i>\n" +
    "                            </td>\n" +
    "\n" +
    "                        </tr>\n" +
    "                    </tbody>\n" +
    "\n" +
    "                </table>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "");
}]);

angular.module("settings-page/settings-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("settings-page/settings-page.tpl.html",
    "<div class=\"page settings-page\">\n" +
    "    <h2>Settings</h2>\n" +
    "\n" +
    "    <div class=\"setting-panel\">\n" +
    "        <h3>Sync data from ORCID</h3>\n" +
    "        <p>\n" +
    "            Your Impactstory profile is built on your ORCID profile, and it\n" +
    "            automatically stays in sync to pull in your new information and new works.\n" +
    "            But if you can't wait, you can also sync manually right now.\n" +
    "        </p>\n" +
    "        <div class=\"sync-controls\">\n" +
    "            <span class=\"btn btn-lg btn-default\"\n" +
    "                  ng-show=\"syncState=='ready'\"\n" +
    "                  ng-click=\"pullFromOrcid()\">\n" +
    "                <i class=\"fa fa-refresh\"></i>\n" +
    "                Sync with my ORCID now\n" +
    "            </span>\n" +
    "            <div class=\"alert alert-info\" ng-show=\"syncState=='working'\">\n" +
    "                <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "                Syncing now...\n" +
    "            </div>\n" +
    "            <div class=\"alert alert-success\" ng-show=\"syncState=='success'\">\n" +
    "                <i class=\"fa fa-check\"></i>\n" +
    "                Sync complete!\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"setting-panel\">\n" +
    "        <h3>Donate</h3>\n" +
    "        <p>Impactstory is a nonprofit dedicated to doing wonderful things\n" +
    "            that involve altmetrics and open science and it's super important.\n" +
    "            But to keep doing that we need money. This Impactstory application you're\n" +
    "            using is free, but if you're getting value out of it, we'd love if\n" +
    "            you could donate to help keep us that way.\n" +
    "        </p>\n" +
    "        <span class=\"btn btn-lg btn-default\">\n" +
    "            <i class=\"fa fa-thumbs-o-up\"></i>\n" +
    "                Donate $10\n" +
    "            </span>\n" +
    "        <span class=\"btn btn-lg btn-default\">\n" +
    "            <i class=\"fa fa-thumbs-o-up\"></i>\n" +
    "            <i class=\"fa fa-thumbs-o-up\"></i>\n" +
    "            Donate $100\n" +
    "        </span>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"setting-panel\">\n" +
    "        <h3>Delete</h3>\n" +
    "        <p>\n" +
    "            Don't like what you see? Drop us a line, we'd love to hear how\n" +
    "            Impactstory could be better. Or you can just delete this profile:\n" +
    "        </p>\n" +
    "        <div class=\"first-q\">\n" +
    "            <span ng-click=\"wantToDelete=true\"\n" +
    "                  ng-show=\"!wantToDelete\"\n" +
    "                  class=\"btn btn-lg btn-default\">\n" +
    "                <i class=\"fa fa-trash\"></i>\n" +
    "                Delete my Impactstory profile\n" +
    "            </span>\n" +
    "        </div>\n" +
    "        <div class=\"second-q\" ng-show=\"wantToDelete\">\n" +
    "            <h4>Are you sure you want to delete your profile?</h4>\n" +
    "            <span ng-click=\"deleteProfile()\"\n" +
    "                  class=\"btn btn-lg btn-danger\">Yes I'm sure!</span>\n" +
    "\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "");
}]);

angular.module("snippet/package-impact-popover.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/package-impact-popover.tpl.html",
    "<div class=\"package impact-popover\">\n" +
    "    <div class=\"impact\">\n" +
    "\n" +
    "        <div class=\"overall\">\n" +
    "            <span class=\"val-plus-label\">\n" +
    "                <span class=\"val\">\n" +
    "                    {{ format.round(package.impact_percentile * 100) }}\n" +
    "                </span>\n" +
    "                <span class=\"ti-label\">percentile <br> overall impact</span>\n" +
    "\n" +
    "            </span>\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"based-on\">\n" +
    "            Compared to other <span class=\"language\">{{ package.language }}</span> research software projects, based on:\n" +
    "        </div>\n" +
    "\n" +
    "        <!-- repeat for each subscore -->\n" +
    "        <div class=\"subscore {{ subscore.name }} metric\"\n" +
    "             ng-if=\"subscore.val > 0\"\n" +
    "             ng-repeat=\"subscore in package.subscores\">\n" +
    "\n" +
    "            <span class=\"bar-outer\">\n" +
    "                <span class=\"bar-inner {{ subscore.name }}\" style=\"width: {{ subscore.percentile * 100 }}%\"></span>\n" +
    "            </span>\n" +
    "\n" +
    "            <span class=\"val pagerank\" ng-if=\"subscore.name=='pagerank'\">{{ format.short(subscore.val, 2) }}</span>\n" +
    "            <span class=\"val\" ng-if=\"subscore.name != 'pagerank'\">{{ format.short(subscore.val) }}</span>\n" +
    "            <span class=\"name\">{{ subscore.display_name }}</span>\n" +
    "        </div>\n" +
    "\n" +
    "    </div>\n" +
    "</div>");
}]);

angular.module("snippet/package-snippet.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/package-snippet.tpl.html",
    "<span class=\"snippet package-snippet is-academic-{{ package.is_academic }}\"\n" +
    "     ng-controller=\"packageSnippetCtrl\">\n" +
    "\n" +
    "    <span class=\"left-metrics is-academic\"\n" +
    "          ng-show=\"package.is_academic\"\n" +
    "          popover-trigger=\"mouseenter\"\n" +
    "          popover-placement=\"bottom\"\n" +
    "         popover-template=\"'snippet/package-impact-popover.tpl.html'\">\n" +
    "\n" +
    "      <div class=\"vis impact-stick\">\n" +
    "            <div ng-repeat=\"subscore in package.subscores\"\n" +
    "                 class=\"bar-inner {{ subscore.name }}\"\n" +
    "                 style=\"width: {{ subscore.percentile * 33.3333 }}%;\">\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "      <div class=\"rank\">\n" +
    "         <span class=\"val\">\n" +
    "            {{ format.round(package.impact_percentile * 100) }}\n" +
    "         </span>\n" +
    "      </div>\n" +
    "\n" +
    "   </span>\n" +
    "\n" +
    "\n" +
    "    <span class=\"left-metrics not-academic\"\n" +
    "          ng-show=\"!package.is_academic\"\n" +
    "          popover=\"Based on name, tags, and description, we're guessing this isn't research software—so we haven't collected detailed impact info.\"\n" +
    "          popover-placement=\"bottom\"\n" +
    "          popover-trigger=\"mouseenter\">\n" +
    "        <span class=\"non-research\">\n" +
    "            non- research\n" +
    "        </span>\n" +
    "\n" +
    "    </span>\n" +
    "\n" +
    "\n" +
    "   <span class=\"metadata is-academic-{{ package.is_academic }}\">\n" +
    "      <span class=\"name-container\">\n" +
    "\n" +
    "         <span class=\"icon\">\n" +
    "            <span class=\"language-icon r\"\n" +
    "                  ng-if=\"package.language=='r'\">\n" +
    "               R\n" +
    "            </span>\n" +
    "            <span class=\"language-icon python\"\n" +
    "                  ng-if=\"package.language=='python'\">\n" +
    "               py\n" +
    "            </span>\n" +
    "         </span>\n" +
    "\n" +
    "\n" +
    "         <a class=\"name\" href=\"package/{{ package.language }}/{{ package.name }}\">\n" +
    "            {{ package.name }}\n" +
    "         </a>\n" +
    "         <i popover-title=\"Research software\"\n" +
    "            popover-trigger=\"mouseenter\"\n" +
    "            popover=\"We decide projects are research software based on their names, tags, and summaries.\"\n" +
    "            ng-show=\"package.is_academic\"\n" +
    "            class=\"is-academic fa fa-graduation-cap\"></i>\n" +
    "\n" +
    "\n" +
    "         <span class=\"contribs\">\n" +
    "            <span class=\"by\">by</span>\n" +
    "            <a href=\"person/{{ contrib.id }}\"\n" +
    "               popover=\"{{ contrib.name }}\"\n" +
    "               popover-trigger=\"mouseenter\"\n" +
    "               class=\"contrib\"\n" +
    "               ng-repeat=\"contrib in package.top_contribs | orderBy: '-credit' | limitTo: 3\">{{ contrib.single_name }}<span\n" +
    "                       ng-hide=\"{{ $last }}\"\n" +
    "                       class=\"comma\">, </span></a><a class=\"contrib plus-more\"\n" +
    "               href=\"package/{{ package.language }}/{{ package.name }}\"\n" +
    "                  popover=\"click to see all {{ package.num_contribs }} contributors\"\n" +
    "                  popover-trigger=\"mouseenter\" ng-show=\"package.num_contribs > 3\">,\n" +
    "               and {{ package.num_contribs - 3 }} others\n" +
    "            </a>\n" +
    "         </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "      </span>\n" +
    "      <span class=\"summary\">{{ package.summary }}</span>\n" +
    "   </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "</span>\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("snippet/person-impact-popover.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/person-impact-popover.tpl.html",
    "<div class=\"person impact-popover\">\n" +
    "   <div class=\"impact\">\n" +
    "       Based on aggregated fractional credit across all research software.\n" +
    "       More details coming soon...\n" +
    "\n" +
    "      <div class=\"sub-score citations metric\" ng-show=\"package.num_citations\">\n" +
    "         <span class=\"name\">\n" +
    "            <i class=\"fa fa-file-text-o\"></i>\n" +
    "            Citations\n" +
    "         </span>\n" +
    "         <span class=\"descr\">\n" +
    "            <span class=\"val\">{{ package.num_citations }}</span>\n" +
    "         </span>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"sub-score pagerank metric\" ng-show=\"package.pagerank\">\n" +
    "         <span class=\"name\">\n" +
    "            <i class=\"fa fa-exchange\"></i>\n" +
    "            Dependency PageRank\n" +
    "         </span>\n" +
    "         <span class=\"descr\">\n" +
    "            <span class=\"val\">{{ format.short(package.pagerank_score) }} </span>\n" +
    "         </span>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"sub-score downloads metric\" ng-show=\"package.num_downloads\">\n" +
    "         <span class=\"name\">\n" +
    "            <i class=\"fa fa-download\"></i>\n" +
    "            Monthly Downloads\n" +
    "         </span>\n" +
    "         <span class=\"descr\">\n" +
    "            <span class=\"val\">{{ format.short(package.num_downloads)}}</span>\n" +
    "         </span>\n" +
    "      </div>\n" +
    "\n" +
    "\n" +
    "   </div>\n" +
    "</div>");
}]);

angular.module("snippet/person-mini.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/person-mini.tpl.html",
    "<span class=\"person-mini-insides\"\n" +
    "   <img src=\"{{ contrib.icon_small }}\" alt=\"\"/>\n" +
    "   <span class=\"impact\">{{ format.short(contrib.impact) }}</span>\n" +
    "   <span class=\"name\">{{ contrib.name }}</span>\n" +
    "</span>");
}]);

angular.module("snippet/person-snippet.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/person-snippet.tpl.html",
    "<span class=\"snippet person-snippet\"\n" +
    "     ng-controller=\"personSnippetCtrl\">\n" +
    "   <span class=\"left-metrics\"\n" +
    "         popover-placement=\"top\"\n" +
    "         popover-title=\"Impact\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover-template=\"'snippet/person-impact-popover.tpl.html'\">\n" +
    "\n" +
    "\n" +
    "      <div class=\"vis impact-stick\">\n" +
    "         <div class=\"bar-inner {{ subscore.name }}\"\n" +
    "              style=\"width: {{ subscore.percentile * 33.33333 }}%;\"\n" +
    "              ng-repeat=\"subscore in person.subscores\">\n" +
    "         </div>\n" +
    "      </div>\n" +
    "\n" +
    "      <span class=\"rank\">\n" +
    "         {{ format.round(person.impact_percentile * 100) }}\n" +
    "      </span>\n" +
    "\n" +
    "   </span>\n" +
    "\n" +
    "\n" +
    "   <span class=\"metadata\">\n" +
    "      <span class=\"name-container\">\n" +
    "\n" +
    "\n" +
    "         <span class=\"icon\">\n" +
    "            <img class=\"person-icon\" src=\"{{ person.icon_small }}\" alt=\"\"/>\n" +
    "         </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "         <a class=\"name\" href=\"person/{{ person.id }}\">\n" +
    "            {{ person.name }}\n" +
    "         </a>\n" +
    "\n" +
    "\n" +
    "         <span class=\"person-packages\">\n" +
    "            <span class=\"works-on\">{{ person.num_packages }} packages including: </span>\n" +
    "            <span class=\"package\" ng-repeat=\"package in person.person_packages | orderBy: '-person_package_impact'\">\n" +
    "               <a href=\"package/{{ package.language }}/{{ package.name }}\">\n" +
    "                  {{ package.name }}</a><span class=\"sep\" ng-show=\"!$last\">,</span>\n" +
    "            </span>\n" +
    "         </span>\n" +
    "      </span>\n" +
    "\n" +
    "      <span class=\"summary tags\">\n" +
    "         <span class=\"tags\">\n" +
    "            <a href=\"tag/{{ format.doubleUrlEncode(tag.name) }}\"\n" +
    "               class=\"tag\"\n" +
    "               ng-repeat=\"tag in person.top_person_tags | orderBy: '-count'\">\n" +
    "               {{ tag.name }}\n" +
    "            </a>\n" +
    "         </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "      </span>\n" +
    "   </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "</span>\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("snippet/tag-snippet.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("snippet/tag-snippet.tpl.html",
    "<span class=\"snippet tag-snippet\"\n" +
    "     ng-controller=\"personSnippetCtrl\">\n" +
    "<span class=\"left-metrics\"\n" +
    "         popover-trigger=\"mouseenter\"\n" +
    "         popover=\"{{ tag.count }} packages are tagged with '{{ tag.name }}'\">\n" +
    "\n" +
    "      <span class=\"one-metric metric\">\n" +
    "         {{ format.short(tag.count) }}\n" +
    "      </span>\n" +
    "\n" +
    "   </span>\n" +
    "\n" +
    "   <span class=\"metadata\">\n" +
    "      <span class=\"name-container\">\n" +
    "\n" +
    "         <span class=\"icon tag-icon\">\n" +
    "            <i class=\"fa fa-tag\"></i>\n" +
    "         </span>\n" +
    "\n" +
    "         <a class=\"name\"\n" +
    "            href=\"tag/{{ format.doubleUrlEncode( tag.name ) }}\">\n" +
    "            {{ tag.name }}\n" +
    "         </a>\n" +
    "\n" +
    "\n" +
    "         <i popover-title=\"Research software\"\n" +
    "            popover-trigger=\"mouseenter\"\n" +
    "            popover=\"This tag is often applied to academic projects.\"\n" +
    "            ng-show=\"tag.is_academic\"\n" +
    "            class=\"is-academic fa fa-graduation-cap\"></i>\n" +
    "\n" +
    "      </span>\n" +
    "\n" +
    "      <span class=\"summary tags\">\n" +
    "         <span class=\"tags\">\n" +
    "            related tags:\n" +
    "            <a href=\"tag/{{ format.doubleUrlEncode( relatedTag.name ) }}\"\n" +
    "               class=\"tag\"\n" +
    "               ng-repeat=\"relatedTag in tag.related_tags | orderBy: '-count'\">\n" +
    "               {{ relatedTag.name }}\n" +
    "            </a>\n" +
    "         </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "      </span>\n" +
    "   </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "</span>\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("static-pages/about.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("static-pages/about.tpl.html",
    "<div class=\"about-page static-page\">\n" +
    "\n" +
    "   <div class=\"coming-soon\">\n" +
    "      <h1>Coming soon:</h1>\n" +
    "      <h2>So many things! We're adding so much over the next few days.</h2>\n" +
    "       <h3>follow us at <a href=\"http://twitter.com/depsy_org\">@depsy_org</a> for updates!</h3>\n" +
    "   </div>\n" +
    "\n" +
    "    <div id=\"readme\" ng-bind-html=\"readme\"></div>\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("static-pages/landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("static-pages/landing.tpl.html",
    "<!-- the landing page for people who are not logged in -->\n" +
    "<div class=\"landing static-page\"\">\n" +
    "    <div class=\"tagline\">\n" +
    "        <h1>\n" +
    "            Find the online impact of your research\n" +
    "        </h1>\n" +
    "        <div class=\"sub\">\n" +
    "            Track buzz on Twitter, blogs, news outlets and more:\n" +
    "            we're like Google Scholar for your research's online reach.\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "    <div>\n" +
    "        <a href ng-click=\"authenticate()\" class=\"btn btn-lg btn-primary\">\n" +
    "            Join for free\n" +
    "        </a>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("static-pages/login.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("static-pages/login.tpl.html",
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "<div class=\"landing static-page\">\n" +
    "    <h3>Logging you in now...</h3>\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);

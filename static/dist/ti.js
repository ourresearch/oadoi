angular.module('aboutPages', [])



    .config(function($routeProvider) {
        $routeProvider.when('/about/data', {
            templateUrl: 'about-pages/about-data.tpl.html',
            controller: 'aboutPageCtrl'
        })
    })

    .config(function($routeProvider) {
        $routeProvider.when('/about/orcid', {
            templateUrl: 'about-pages/about-orcid.tpl.html',
            controller: 'aboutPageCtrl'
        })
    })

    .config(function($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: 'about-pages/about.tpl.html',
            controller: 'aboutPageCtrl'
        })
    })

    .config(function($routeProvider) {
        $routeProvider.when('/search', {
            templateUrl: 'about-pages/search.tpl.html',
            controller: 'searchPageCtrl'
        })
    })

    .config(function($routeProvider) {
        $routeProvider.when('/about/achievements', {
            templateUrl: 'about-pages/about-badges.tpl.html',
            controller: 'aboutPageCtrl',
            resolve: {
                badgesResp: function($http, $route, BadgeDefs){
                    console.log("loaded the badge defs in the route def")
                    return BadgeDefs.load()
                }
            }
        })
    })

    .controller("searchPageCtrl", function($scope, $http, $location){
        $scope.ctrl = {}

        $scope.onSearchSelect = function(selection){
            console.log("selection!", selection)
            $scope.loading = true
            $location.url("u/" + selection.orcid_id)

        }

        $scope.search = function(searchName) {
            return $http.get("api/search/" + searchName)
                .then(function(resp){
                    console.log("got search results back", resp)
                    return resp.data.list
                })
        }
        $http.get("/api/people")
            .success(function(resp){
                $scope.numProfiles = resp.count
            })
    })


    .controller("aboutPageCtrl", function($scope,
                                          $auth,
                                           $routeParams,
                                           BadgeDefs){
        $scope.badgeDefs = BadgeDefs

        // copied from person page
        var subscoreSortOrder = {
            buzz: 1,
            engagement: 2,
            openness: 3,
            fun: 4
        }

        // convert to a list in a kinda dumb way, whatevs.
        var badgesList = []
        _.each(BadgeDefs.d, function(v, k){
            var myBadge = _.extend({}, v);
            myBadge.id = k
            myBadge.description = myBadge.description.replace("{value}", "<em class='n'>n</em>")
            badgesList.push(myBadge)
        })

        console.log("badges", badgesList)




        // group the badges by Badge Group
        var badgesByGroup = _.groupBy(badgesList, "group")
        var badgeGroups = []
        _.each(badgesByGroup, function(badges, groupName){
            console.log("group name" , groupName)
            if (groupName  && groupName != "null"){ // hack
                badgeGroups.push({
                    name: groupName,
                    sortLevel: subscoreSortOrder[groupName],
                    badges: badges
                })
            }

        })

        $scope.badgeGroups = badgeGroups

        // group everything by Aggregation Level (person or product)
        //var badges = _.groupBy(badgeGroups, "aggregationLevel")
        //$scope.badges = badges





        //if ($auth.isAuthenticated()){
        //    var myOrcidId = $auth.getPayload()["sub"]
        //    Person.load(myOrcidId).success(function(resp){
        //        console.log("loaded the person", Person.d)
        //        $scope.iHaveThisBadge = function(badgeId){
        //            return _.findWhere(Person.d.badges, {name: badgeId})
        //        }
        //    })
        //}









    })




angular.module('app', [
    // external libs

    'ngRoute',
    'ngMessages',
    'satellizer',

    'ngResource',
    'ngSanitize',
    'ngMaterial',

    'templates.app',  // this is how it accesses the cached templates in ti.js

    'staticPages',

    'badgeDefs',
    'personPage',
    'productPage',
    'settingsPage',
    'badgePage',
    'aboutPages',

    'numFormat'

]);




angular.module('app').config(function ($routeProvider,
                                       $authProvider,
                                       $mdThemingProvider,
                                       $locationProvider) {


    $locationProvider.html5Mode(true);

    // handle 404s by redirecting to landing page.
    $routeProvider.otherwise({ redirectTo: '/' })

    $mdThemingProvider.theme('default')
        .primaryPalette('deep-orange')
        .accentPalette("blue")


    var orcidLoginSettings = {
        name: "orcid-login",
        url: "/api/auth/orcid",
        clientId: "APP-PF0PDMP7P297AU8S",
        redirectUri: window.location.origin + "/login",
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
    }
    $authProvider.oauth2(orcidLoginSettings)

    // this is for when we know the user has no ORCID,
    // so we want to redirect them to "sign up for ORCID" oath
    // screen instead of the "sign in to ORCID" screen like normal
    var orcidRegisterSettings = angular.copy(orcidLoginSettings)
    orcidRegisterSettings.name = "orcid-register"
    orcidRegisterSettings.showLogin = "false"
    $authProvider.oauth2(orcidRegisterSettings)






});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $auth,
                                   $location) {


    (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
            (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
        m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

    ga('create', 'UA-23384030-1', 'auto');


    $rootScope.$on('$routeChangeStart', function(next, current){
    })
    $rootScope.$on('$routeChangeSuccess', function(next, current){
        window.scrollTo(0, 0)
        ga('send', 'pageview', { page: $location.url() });

    })

    // load the intercom user
    var me = $auth.getPayload();
    if (me){
        var claimed_at = moment(me.claimed_at).unix()
        var intercomInfo = {
            app_id: "z93rnxrs",
            name: me.given_names + " " + me.family_name,
            user_id: me.sub, // orcid ID
            claimed_at: claimed_at
          }
        Intercom('boot', intercomInfo)
    }






    $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
        console.log("$routeChangeError")
        $location.path("/")
        window.scrollTo(0, 0)
    });




});





angular.module('app').controller('AppCtrl', function(
    $rootScope,
    $scope,
    $route,
    $location,
    NumFormat,
    $auth,
    $interval,
    $http,
    $mdDialog,
    $sce){

    $scope.auth = $auth
    $scope.numFormat = NumFormat
    $scope.moment = moment // this will break unless moment.js loads over network...

    $scope.global = {}

    $scope.pageTitle = function(){
        if (!$scope.global.title){
            $scope.global.title = "Discover the online impact of your research"
        }
        return "Impactstory: " + $scope.global.title
    }


    $rootScope.$on('$routeChangeSuccess', function(next, current){
        $scope.global.showBottomStuff = true
        $scope.global.loggingIn = false
        $scope.global.title = null
    })

    $scope.trustHtml = function(str){
        return $sce.trustAsHtml(str)
    }
    $scope.pluralize = function(noun, number){
        //pluralize.addSingularRule(/slides$/i, 'slide deck')
        return pluralize(noun, number)
    }



    // config stuff
    // badge group configs
    var badgeGroupIcons = {
        engagement: "user",
        openness: "unlock-alt",
        buzz: "bullhorn",
        fun: "smile-o"
    }
    $scope.getBadgeIcon = function(group){
        if (badgeGroupIcons[group]){
            return badgeGroupIcons[group]
        }
        else {
            return "fa-trophy"
        }
    }

    // genre config
    var genreIcons = {
        'article': "file-text-o",
        'blog': "comments",
        'dataset': "table",
        'figure': "bar-chart",
        'poster': "picture",
        'slides': "desktop",
        'software': "save",
        'twitter': "twitter",
        'video': "facetime-video",
        'webpage': "laptop",
        'online-resource': "desktop",
        'preprint': "paper-plane-o",
        'other': "ellipsis-h",
        'unknown': "ellipsis-h",
        "conference paper": "list-alt",  // conference proceeding
        "book": "book",
        "book chapter": "bookmark-empty",  // chapter anthology
        "thesis": "graduation-cap",
        "dissertation": "graduation-cap",
        "peer review": "comment-alt"
    }
    $scope.getGenreIcon = function(genre){
        if (genreIcons[genre]){
            return genreIcons[genre]
        }
        else {
            return genreIcons.unknown
        }
    }







    var redirectUri = window.location.origin + "/login"
    var orcidAuthUrl = "https://orcid.org/oauth/authorize" +
        "?client_id=APP-PF0PDMP7P297AU8S" +
        "&response_type=code" +
        "&scope=/authenticate" +
        "&redirect_uri=" + redirectUri

    // used in the nav bar, also for signup on the landing page.
    var authenticate = function (showLogin) {
        console.log("authenticate!")

        if (showLogin == "signin"){
            // will show the signup screen
        }
        else {
            // show the login screen (defaults to this)
            orcidAuthUrl += "&show_login=true"
        }

        window.location = orcidAuthUrl
        return true

    }

    $rootScope.authenticate = authenticate
    $scope.authenticate = authenticate

    var showAlert = function(msgText, titleText, okText){
        if (!okText){
            okText = "ok"
        }
          $mdDialog.show(
                  $mdDialog.alert()
                    .clickOutsideToClose(true)
                    .title(titleText)
                    .textContent(msgText)
                    .ok(okText)
            );
    }
    $rootScope.showAlert = showAlert









    /********************************************************
     *
     *  stripe stuff
     *
    ********************************************************/



    var stripeInfo = {
        email: null,
        tokenId: null,
        cents: 0,

        // optional
        fullName: null,
        orcidId: null
    }

    var stripeHandler = StripeCheckout.configure({
        key: stripePublishableKey,
        locale: 'auto',
        token: function(token) {
            stripeInfo.email = token.email
            stripeInfo.tokenId = token.id

            console.log("now we are doing things with the user's info", stripeInfo)
            $http.post("/api/donation", stripeInfo)
                .success(function(resp){
                    console.log("the credit card charge worked!", resp)
                    showAlert(
                        "We appreciate your donation, and we've emailed you a receipt.",
                        "Thanks so much!"
                    )
                })
                .error(function(resp){
                    console.log("error!", resp.message)
                    if (resp.message){
                        var reason = resp.message
                    }
                    else {
                        var reason = "Sorry, we had a server error! Drop us a line at team@impactstory.org and we'll fix it."
                    }
                    showAlert(reason, "Credit card error")
                })
        }
      });
    $scope.donate = function(cents){
        console.log("donate", cents)
        stripeInfo.cents = cents
        var me = $auth.getPayload() // this might break on the donate page.
        if (me){
            stripeInfo.fullName = me.given_names + " " + me.family_name
            stripeInfo.orcidId = me.sub
        }

        stripeHandler.open({
          name: 'Impactstory donation',
          description: "We're a US 501(c)3",
          amount: cents
        });
    }


})



.controller('badgeItemCtrl', function($scope){
    $scope.showMaxItems = 3
    $scope.getIconUrl = function(name){
    }
})

.controller('tweetRollupCtrl', function($scope){
    $scope.showTweets = false
})

.directive('subscorehelp', function(){
        return {
            restrict: "E",
            templateUrl: 'helps.tpl.html',
            scope:{
                subscoreName: "=name"
            },
            link: function(scope, elem, attrs){
            }
        }
    })

.directive('short', function(){
        return {
            restrict: "E",
            template: '{{shortText}}<span ng-show="shortened">&hellip;</span>',
            scope:{
                text: "=text",
                len: "=len"
            },
            link: function(scope, elem, attrs){

                var newLen
                if (scope.len) {
                    newLen = scope.len
                }
                else {
                    newLen = 40
                }
                if (scope.text.length > newLen){
                    var short = scope.text.substring(0, newLen)
                    short = short.split(" ").slice(0, -1).join(" ")
                    scope.shortText = short
                    scope.shortened = true
                }
                else {
                    scope.shortText = scope.text
                }

            }
        }
    })















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
        $routeProvider.when('/u/:orcid/:tab?/:filter?', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            reloadOnSearch: false,
            resolve: {
                personResp: function($http, $route, Person){
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $auth,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){



        $scope.global.title = Person.d.given_names + " " + Person.d.family_name
        $scope.person = Person.d
        $scope.products = Person.d.products
        $scope.sources = Person.d.sources
        $scope.badges = Person.d.badges
        $scope.d = {}

        var ownsThisProfile = $auth.isAuthenticated() && $auth.getPayload().sub == Person.d.orcid_id



        console.log("retrieved the person", $auth.isAuthenticated(), $scope.person)

        $scope.profileStatus = "all_good"
        $scope.tab =  $routeParams.tab || "overview"
        $scope.userForm = {}

        if (ownsThisProfile && !Person.d.email ) {
            $scope.profileStatus = "no_email"
        }
        else if (ownsThisProfile && !Person.d.num_orcid_products) {
            $scope.profileStatus = "no_products"
        }
        else {
            $scope.profileStatus = "all_good"
        }

        $scope.settingEmail = false
        $scope.submitEmail = function(){
            console.log("setting the email!", $scope.userForm.email)
            $scope.settingEmail = true
            $http.post("/api/me", {email: $scope.userForm.email})
                .success(function(resp){
                    // force the person to reload
                    console.log("reloading the Person")
                    Person.reload().then(
                        function(resp){
                            $scope.profileStatus = "all_good"
                            console.log("success, reloading page.")
                            $route.reload()
                        }
                    )
                })
        }


        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.syncing = true
            $http.post("/api/me", {action: "pull_from_orcid"})
                .success(function(resp){
                    // force the person to reload
                    console.log("reloading the Person")
                    Person.reload().then(
                        function(resp){
                            $scope.profileStatus = "all_good"
                            console.log("success, reloading page.")
                            $route.reload()
                        }
                    )
                })
        }

        $scope.follow = function(){
            console.log("ya follow?")
        }







        // posts and mentions stuff
        var posts = []
        _.each(Person.d.products, function(product){
            var myDoi = product.doi
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
                myPost.citesTitle = myTitle
                posts.push(myPost)
            })
        })

        function makePostsWithRollups(posts){
            var sortedPosts = _.sortBy(posts, "posted_on")
            var postsWithRollups = []
            function makeRollupPost(){
                return {
                    source: 'tweetRollup',
                    posted_on: '',
                    count: 0,
                    tweets: []
                }
            }
            var currentRollup = makeRollupPost()
            _.each(sortedPosts, function(post){
                if (post.source == 'twitter'){

                    // we keep tweets as regular posts too
                    postsWithRollups.push(post)

                    // put the tweet in the rollup
                    currentRollup.tweets.push(post)

                    // rollup posted_on date will be date of *first* tweet in group
                    if (!currentRollup.posted_on){
                        currentRollup.posted_on = post.posted_on
                    }
                }
                else {
                    postsWithRollups.push(post)

                    // save the current rollup
                    if (currentRollup.tweets.length){
                        postsWithRollups.push(currentRollup)
                    }

                    // clear the current rollup
                    currentRollup = makeRollupPost()
                }
            })

            // there may be rollup still sitting around because no regular post at end
            if (currentRollup.tweets.length){
                postsWithRollups.push(currentRollup)
            }
            return postsWithRollups
        }

        $scope.posts = makePostsWithRollups(posts)
        $scope.postsFilter = function(post){
            if ($scope.selectedChannel) {
                return post.source == $scope.selectedChannel.source_name
            }
            else { // we are trying to show unfiltered view

                // but even in unfiltered view we want to hide tweets.
                return post.source != 'twitter'

            }
        }

        $scope.postsSum = 0
        _.each(Person.d.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.d.postsLimit = 20
        $scope.selectedChannel = _.findWhere(Person.d.sources, {source_name: $routeParams.filter})

        $scope.toggleSelectedChannel = function(channel){
            console.log("toggling selected channel", channel)
            if (channel.source_name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/mentions")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/mentions/" + channel.source_name)
            }
        }










        // genre stuff
        var genreGroups = _.groupBy(Person.d.products, "genre")
        var genres = []
        _.each(genreGroups, function(v, k){
            genres.push({
                name: k,
                display_name: k.split("-").join(" "),
                count: v.length
            })
        })
        console.log("genres", genres)

        $scope.genres = genres
        $scope.selectedGenre = _.findWhere(genres, {name: $routeParams.filter})
        console.log("$scope.selectedGenre", $scope.selectedGenre)
        $scope.toggleSeletedGenre = function(genre){
            if (genre.name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/publications")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/publications/" + genre.name)
            }
        }











        // achievements stuff
        var subscoreSortOrder = {
            buzz: 1,
            engagement: 2,
            openness: 3,
            fun: 4
        }

        // put the badge counts in each subscore
        var subscores = _.map(Person.d.subscores, function(subscore){
            var matchingBadges = _.filter(Person.d.badges, function(badge){
                return badge.group == subscore.name
            })
            subscore.badgesCount = matchingBadges.length
            subscore.sortOrder = subscoreSortOrder[subscore.name]
            return subscore
        })
        $scope.subscores = subscores
        $scope.selectedSubscore = _.findWhere(subscores, {name: $routeParams.filter})

        $scope.toggleSeletedSubscore = function(subscore){
            console.log("toggle subscore", subscore)
            if (subscore.name == $routeParams.filter){
                $location.url("u/" + Person.d.orcid_id + "/achievements")
            }
            else {
                $location.url("u/" + Person.d.orcid_id + "/achievements/" + subscore.name)
            }
        }









    })




angular.module('productPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/doi/:id*/:filter?', {
            templateUrl: 'product-page/product-page.tpl.html',
            controller: 'productPageCtrl'
            ,
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("productPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){


        var possibleChannels = _.pluck(Person.d.sources, "source_name")
        console.log("possibleChannels", possibleChannels, $routeParams.filter)
        var doi
        if (_.contains(possibleChannels, $routeParams.filter)) {
            // do filter stuff. this is not just part of the DOI
            console.log("we have a real filter", $routeParams.filter)
            doi = $routeParams.id
        }
        else {
            // crazy hack! this is how we are dealing with there
            // being slashes in the DOI.
            doi = $routeParams.id + "/" + $routeParams.filter
            console.log("no real filter. making the doi", doi)
        }

        var product = _.findWhere(Person.d.products, {doi: doi})

        $scope.person = Person.d
        $scope.sources = product.sources
        $scope.doi = doi
        $scope.product = product
        $scope.d = {}

        console.log("$scope.product", $scope.product, $routeParams.filter)




        function makePostsWithRollups(posts){
            var sortedPosts = _.sortBy(posts, "posted_on")
            var postsWithRollups = []
            function makeRollupPost(){
                return {
                    source: 'tweetRollup',
                    posted_on: '',
                    count: 0,
                    tweets: []
                }
            }
            var currentRollup = makeRollupPost()
            _.each(sortedPosts, function(post){
                if (post.source == 'twitter'){

                    // we keep tweets as regular posts too
                    postsWithRollups.push(post)

                    // put the tweet in the rollup
                    currentRollup.tweets.push(post)

                    // rollup posted_on date will be date of *first* tweet in group
                    if (!currentRollup.posted_on){
                        currentRollup.posted_on = post.posted_on
                    }
                }
                else {
                    postsWithRollups.push(post)

                    // save the current rollup
                    if (currentRollup.tweets.length){
                        postsWithRollups.push(currentRollup)
                    }

                    // clear the current rollup
                    currentRollup = makeRollupPost()
                }
            })

            // there may be rollup still sitting around because no regular post at end
            if (currentRollup.tweets.length){
                postsWithRollups.push(currentRollup)
            }
            return postsWithRollups
        }

        $scope.posts = makePostsWithRollups(product.posts)
        $scope.postsFilter = function(post){
            if ($scope.selectedChannel) {
                return post.source == $scope.selectedChannel.source_name
            }
            else { // we are trying to show unfiltered view

                // but even in unfiltered view we want to hide tweets.
                return post.source != 'twitter'

            }
        }

        $scope.postsSum = 0
        _.each($scope.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.d.postsLimit = 20
        $scope.selectedChannel = _.findWhere(Person.d.sources, {source_name: $routeParams.filter})

        $scope.toggleSelectedChannel = function(channel){
            console.log("toggling selected channel", channel)
            var rootUrl = "u/" + Person.d.orcid_id + "/doi/" + doi
            if (channel.source_name == $routeParams.filter){
                $location.url(rootUrl)
            }
            else {
                $location.url(rootUrl + "/" + channel.source_name)
            }
        }




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


            if (num < 1) {
                return Math.round(num * 100) / 100;  // to two decimals
            }

            return Math.ceil(num);
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

        var decimalToPerc = function(decimal, asOrdinal){
            var ret = Math.round(decimal * 100)
            if (asOrdinal){
                ret = ordinal(ret)
            }
            return ret
        }
        return {
            short: short,
            commas: commas,
            round: round,
            ordinal: ordinal,
            doubleUrlEncode: doubleUrlEncode,
            decimalToPerc: decimalToPerc

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



    .factory("Person", function($http, $q){

        var data = {}
        var badgeSortLevel = {
            "gold": 1,
            "silver": 2,
            "bronze": 3
        }
        var beltDescriptions = {
            white: "initial",
            yellow: "promising",
            orange: "notable",
            brown: "extensive",
            black: "exceptional"
        }

        function load(orcidId, force){


            // if the data for this profile is already loaded, just return it
            // unless we've been told to force a refresh from the server.
            if (data.orcid_id == orcidId && !force){
                console.log("Person Service getting from cache:", orcidId)
                return $q.when(data)
            }


            var url = "/api/person/" + orcidId
            console.log("Person Service getting from server:", orcidId)
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
                enrichedBadge.sortLevel = badgeSortLevel[enrichedBadge.level]
                ret.push(enrichedBadge)
            })

            return ret
        }

        return {
            d: data,
            load: load,
            getBadgesWithConfigs: getBadgesWithConfigs,
            reload: function(){
                return load(data.orcid_id, true)
            }
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



    .controller("settingsPageCtrl", function($scope, $auth, $route, $location, $http, Person){

        console.log("the settings page loaded")
        $scope.orcidId = $auth.getPayload()["sub"]
        $scope.givenNames = $auth.getPayload()["given_names"]

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
                    // force a reload of the person
                    Person.load($auth.getPayload().sub, true).then(
                        function(resp){
                            $scope.syncState = "success"
                            console.log("we reloaded the Person after sync")
                        }
                    )
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
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginCtrl"
        })
    })



    .controller("LoginCtrl", function ($scope, $location, $http, $auth) {
        console.log("kenny loggins page controller is running!")


        var searchObject = $location.search();
        var code = searchObject.code
        if (!code){
            $location.path("/")
            return false
        }

        var requestObj = {
            code: code,
            redirectUri: window.location.origin + "/login"
        }

        $http.post("api/auth/orcid", requestObj)
            .success(function(resp){
                console.log("got a token back from ye server", resp)
                $auth.setToken(resp.token)
                var payload = $auth.getPayload()
                var created = moment(payload.created).unix()
                var intercomInfo = {
                    app_id: "z93rnxrs",
                    name: payload.given_names + " " + payload.family_name,
                    user_id: payload.sub, // orcid ID
                    created_at: created
                  }

                Intercom('boot', intercomInfo)
                $location.url("u/" + payload.sub)
            })
            .error(function(resp){
              console.log("problem getting token back from server!", resp)
                $location.url("/")
            })






    })

    .controller("LandingPageCtrl", function ($scope,
                                             $mdDialog,
                                             $rootScope,
                                             $timeout) {
        $scope.global.showBottomStuff = false;
        console.log("landing page!", $scope.global)

        var orcidModalCtrl = function($scope){
            console.log("IHaveNoOrcidCtrl ran" )
            $scope.modalAuth = function(){
                $mdDialog.hide()
            }
        }

        $scope.noOrcid = function(ev){
            $mdDialog.show({
                controller: orcidModalCtrl,
                templateUrl: 'orcid-dialog.tmpl.html',
                clickOutsideToClose:true,
                targetEvent: ev
            })
                .then(
                function(){
                    $rootScope.authenticate("signin")
                },
                function(){
                    console.log("they cancelled the dialog")
                }
            )


        }

    })
    .controller("IHaveNoOrcidCtrl", function($scope){
        console.log("IHaveNoOrcidCtrl ran" )
    })











angular.module('templates.app', ['about-pages/about-badges.tpl.html', 'about-pages/about-data.tpl.html', 'about-pages/about-orcid.tpl.html', 'about-pages/about.tpl.html', 'about-pages/search.tpl.html', 'badge-page/badge-page.tpl.html', 'footer/footer.tpl.html', 'header/header.tpl.html', 'header/search-result.tpl.html', 'helps.tpl.html', 'package-page/package-page.tpl.html', 'person-page/person-page-text.tpl.html', 'person-page/person-page.tpl.html', 'product-page/product-page.tpl.html', 'settings-page/settings-page.tpl.html', 'sidemenu.tpl.html', 'snippet/package-impact-popover.tpl.html', 'snippet/package-snippet.tpl.html', 'snippet/person-impact-popover.tpl.html', 'snippet/person-mini.tpl.html', 'snippet/person-snippet.tpl.html', 'snippet/tag-snippet.tpl.html', 'static-pages/landing.tpl.html', 'static-pages/login.tpl.html', 'workspace.tpl.html']);

angular.module("about-pages/about-badges.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("about-pages/about-badges.tpl.html",
    "<div class=\"page about-badges\">\n" +
    "    <h2>Impactstory achievements</h2>\n" +
    "    <div class=\"intro\">\n" +
    "        <p>Achievements are a way of looking beyond the numbers to find stories that matter:\n" +
    "            stories the buzz your research is generating, the level of engagement with your work,\n" +
    "            your openness, and some lighthearted fun from time to time.\n" +
    "\n" +
    "        </p>\n" +
    "    </div>\n" +
    "    <div class=\"main\">\n" +
    "\n" +
    "        <div class=\"badge-group\" ng-repeat=\"badgeGroup in badgeGroups | orderBy: 'sortLevel'\">\n" +
    "            <div class=\"about {{ badgeGroup.name }}\">\n" +
    "                <h4 class=\"badge-group {{ badgeGroup.name }}\">\n" +
    "                    <i class=\"fa fa-{{ getBadgeIcon(badgeGroup.name) }}\"></i>\n" +
    "                    <span class=\"name\">{{ badgeGroup.name }}</span>\n" +
    "                </h4>\n" +
    "\n" +
    "\n" +
    "                <p class=\"def buzz\" ng-show=\"badgeGroup.name=='buzz'\">\n" +
    "                    <strong>Buzz</strong> is the volume of discussion (good and bad)\n" +
    "                    around your research. It's a good&mdash;if coarse&mdash;measure of online interest around\n" +
    "                    your work.\n" +
    "                </p>\n" +
    "                <p class=\"def engagement\" ng-show=\"badgeGroup.name=='engagement'\">\n" +
    "                    <strong>Engagement</strong> is about <em>how</em> your work is mentioned, accounting\n" +
    "                    for the different impacts of different sources: Wikipedia counts for more than Facebook, and a tweeter\n" +
    "                    with a million followers counts for more than one with a hundred.\n" +
    "                </p>\n" +
    "                <p class=\"def openness\" ng-show=\"badgeGroup.name=='openness'\">\n" +
    "                    <strong>Openness</strong> looks at how easy it is for people to actually read and use\n" +
    "                    your research; publishing in Open Access venues is a big part of this, but so is\n" +
    "                    publishing open data and code, and publishing in ways that build lay and practioner\n" +
    "                    audiences.\n" +
    "\n" +
    "                </p>\n" +
    "                <p class=\"def fun\" ng-show=\"badgeGroup.name=='fun'\">\n" +
    "                    <strong>Fun</strong> achievements are Not So Serious.\n" +
    "\n" +
    "                </p>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "            <div class=\"badges-wrapper row\"\n" +
    "                 ng-include=\"'badge-item.tpl.html'\"\n" +
    "                 ng-repeat=\"badge in badgeGroup.badges\">\n" +
    "\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "</div>");
}]);

angular.module("about-pages/about-data.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("about-pages/about-data.tpl.html",
    "<div class=\"page about about-data\">\n" +
    "\n" +
    "    <img src=\"http://www.123gifs.eu/free-gifs/underconstruction/underconstruction-0193.gif\" alt=\"\">\n" +
    "    \n" +
    "    <h3 id=\"engagement-score\">Engagement score</h3>\n" +
    "    <p>\n" +
    "        We're currently working on this section. Stay tuned, we'll have more\n" +
    "        here by the end of today\n" +
    "    </p>\n" +
    "    <h3 id=\"data-sources\">Data sources</h3>\n" +
    "    <p>\n" +
    "        We're currently working on this section. Stay tuned, we'll have more\n" +
    "        here by the end of today\n" +
    "    </p>\n" +
    "    <h3 id=\"metrics\">Metrics</h3>\n" +
    "    <p>\n" +
    "        We're currently working on this section. Stay tuned, we'll have more\n" +
    "        here by the end of today\n" +
    "    </p>\n" +
    "\n" +
    "\n" +
    "</div>");
}]);

angular.module("about-pages/about-orcid.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("about-pages/about-orcid.tpl.html",
    "<div class=\"page about about-orcid\">\n" +
    "    <h2>Impactstory and ORCID</h2>\n" +
    "\n" +
    "    <h3>Auto-generated profiles</h3>\n" +
    "    <p>\n" +
    "        ORCID users control all access to their data, but many ORCID users choose to make their data public.\n" +
    "    </p>\n" +
    "    <p>\n" +
    "        We've used open data from public ORCID profiles to help us auto-generate some Impactstory profiles. These\n" +
    "        auto-generated profiles help us build robust percentile information, since we can compare any given\n" +
    "        user to a nice large set of scholars at large.\n" +
    "    </p>\n" +
    "    <p>\n" +
    "        If you've got an auto-generated ORCID profile, you'll probably want to log in to claim it&mdash;it's\n" +
    "        as simple as logging in to your ORCID account and takes just a few seconds. Once you've logged in,\n" +
    "        you can get start getting email updates on new online impacts, as well as also modify or delete your\n" +
    "        profile if you'd like.\n" +
    "    </p>\n" +
    "    <p>\n" +
    "        If you have any trouble logging in, just drop us a line and we'll be glad to help.\n" +
    "    </p>\n" +
    "\n" +
    "\n" +
    "\n" +
    "</div>");
}]);

angular.module("about-pages/about.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("about-pages/about.tpl.html",
    "<div class=\"page about about-page\" id=\"about\">\n" +
    "\n" +
    "   <div class=\"wrapper\">\n" +
    "      <h2 class=\"infopage-heading\">About</h2>\n" +
    "\n" +
    "\n" +
    "      <p>Impactstory is an open-source, web-based tool that helps scientists explore and share the diverse\n" +
    "          impacts of all their research products.\n" +
    "\n" +
    "          By helping scientists tell data-driven stories about their impacts,\n" +
    "          we're helping to build a new scholarly reward system that values and encourages web-native scholarship.\n" +
    "          We’re funded by the National Science Foundation and the Alfred P. Sloan Foundation and\n" +
    "          incorporated as a 501(c)(3) nonprofit corporation.\n" +
    "\n" +
    "      <!--\n" +
    "      <p>Impactstory delivers <em>open metrics</em>, with <em>context</em>, for <em>diverse products</em>:</p>\n" +
    "      <ul>\n" +
    "         <li><b>Open metrics</b>: Our data (to the extent allowed by providers’ terms of service), <a href=\"https://github.com/total-impact\">code</a>, and <a href=\"http://blog.impactstory.org/2012/03/01/18535014681/\">governance</a> are all open.</li>\n" +
    "         <li><b>With context</b>: To help scientists move from raw <a href=\"http://altmetrics.org/manifesto/\">altmetrics</a> data to <a href=\"http://asis.org/Bulletin/Apr-13/AprMay13_Piwowar_Priem.html\">impact profiles</a> that tell data-driven stories, we sort metrics by <em>engagement type</em> and <em>audience</em>. We also normalize based on comparison sets: an evaluator may not know if 5 forks on GitHub is a lot of attention, but they can understand immediately if their project ranked in the 95th percentile of all GitHub repos created that year.</li>\n" +
    "         <li><b>Diverse products</b>: Datasets, software, slides, and other research products are presented as an integrated section of a comprehensive impact report, alongside articles&mdash;each genre a first-class citizen, each making its own kind of impact.</li>\n" +
    "      </ul>\n" +
    "      -->\n" +
    "\n" +
    "      <h3 id=\"team\">team</h3>\n" +
    "\n" +
    "      <div class=\"team-member first\">\n" +
    "         <img src=\"/static/img/heather.jpg\" height=100/>\n" +
    "         <p><strong>Heather Piwowar</strong> is a cofounder of Impactstory and a leading researcher in research data availability and data reuse. She wrote one of the first papers measuring the <a href=\"http://www.plosone.org/article/info:doi/10.1371/journal.pone.0000308\">citation benefit of publicly available research data</a>, has studied  <a href=\"http://www.plosone.org/article/info:doi/10.1371/journal.pone.0018657\">patterns in  data archiving</a>, <a href=\"https://peerj.com/preprints/1/\">patterns of data reuse</a>, and the <a href=\"http://researchremix.wordpress.com/2010/10/12/journalpolicyproposal\">impact of journal data sharing policies</a>.</p>\n" +
    "\n" +
    "         <p>Heather has a bachelor’s and master’s degree from MIT in electrical engineering, 10 years of experience as a software engineer, and a Ph.D. in Biomedical Informatics from the U of Pittsburgh.  She is an <a href=\"http://www.slideshare.net/hpiwowar\">frequent speaker</a> on research data archiving, writes a well-respected <a href=\"http://researchremix.wordpress.com\">research blog</a>, and is active on twitter (<a href=\"http://twitter.com/researchremix\">@researchremix</a>). </p>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"team-member subsequent\">\n" +
    "         <img src=\"/static/img/jason.jpg\" height=100/>\n" +
    "         <p><strong>Jason Priem</strong> is a cofounder of Impactstory and a doctoral student in information science (currently on leave of absence) at the University of North Carolina-Chapel Hill. Since <a href=\"https://twitter.com/jasonpriem/status/25844968813\">coining the term \"altmetrics,\"</a> he's remained active in the field, organizing the annual <a href=\"http:altmetrics.org/altmetrics12\">altmetrics workshops</a>, giving <a href=\"http://jasonpriem.org/cv/#invited\">invited talks</a>, and publishing <a href=\"http://jasonpriem.org/cv/#refereed\">peer-reviewed altmetrics research.</a></p>\n" +
    "\n" +
    "         <p>Jason has contributed to and created several open-source software projects, including <a href=\"http://www.zotero.org\">Zotero</a> and <a href=\"http://feedvis.com\">Feedvis</a>, and has experience and training in art, design, and information visualisation.  Sometimes he writes on a <a href=\"http://jasonpriem.org/blog\">blog</a> and <a href=\"https://twitter.com/#!/jasonpriem\">tweets</a>.</p>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"clearfix\"></div>\n" +
    "\n" +
    "\n" +
    "      <h3 id=\"history\">history</h3>\n" +
    "      <p>Impactstory began life as total-impact, a hackathon project at the Beyond Impact workshop in 2011. As the hackathon ended, a few of us migrated into a hotel hallway to continue working, eventually completing a 24-hour coding marathon to finish a prototype. Months of spare-time development followed, then funding.  We’ve got the same excitement for Impactstory today.</p>\n" +
    "\n" +
    "      <p>In early 2012, Impactstory was given £17,000 through the <a href=\"http://beyond-impact.org/\">Beyond Impact project</a> from the <a href=\"http://www.soros.org/\">Open Society Foundation</a>.  Today Impactstory is funded by the <a href=\"http://sloan.org/\">Alfred P. Sloan Foundation</a>, first through <a href=\"http://blog.impactstory.org/2012/03/29/20131290500/\">a $125,000 grant</a> in mid 2012 and then <a href=\"http://blog.impactstory.org/2013/06/17/sloan/\">a two-year grant for $500,000</a> starting in 2013.  We also received <a href=\"http://blog.impactstory.org/2013/09/27/impactstory-awarded-300k-nsf-grant/\">a $300,000 grant</a> from the National Science Foundation to study how automatically-gathered impact metrics can improve the reuse of research software. </p>\n" +
    "\n" +
    "      <h3 id=\"why\">philosophy</h3>\n" +
    "      <p>As a philanthropically-funded not-for-profit, we're in this because we believe open altmetrics are key for building the coming era of Web-native science. We're committed to:</p>\n" +
    "      <ul>\n" +
    "         <li><a href=\"https://github.com/total-impact\">open source</a></li>\n" +
    "         <li><a href=\"http://blog.impactstory.org/2012/06/08/24638498595/\">free and open data</a>, to the extent permitted by data providers</li>\n" +
    "         <li><a href=\"http://en.wikipedia.org/wiki/Radical_transparency\">Radical transparency</a> and <a href=\"http://blog.impactstory.org\">open communication</a></li>\n" +
    "      </ul>\n" +
    "\n" +
    "      <h3 id=\"board\">board of directors</h3>\n" +
    "\n" +
    "      <div class=\"board-member\">\n" +
    "         <img src=\"http://i.imgur.com/G4wUQb8.png\" height=100/>\n" +
    "         <p><strong>Heather Joseph</strong> is the Executive Director of the <a href=\"http://www.sparc.arl.org/\">Scholarly Publishing and Academic Resources Coalition (SPARC)</a> and the convener of the\n" +
    "            <a href=\"http://www.taxpayeraccess.org/\">Alliance for Taxpayer Access</a>. Prior to coming to SPARC, she spent 15 years as a publisher in both commercial and not-for-profit publishing organizations. She served as the publishing director at the American Society for Cell Biology, which became the first journal to commit its full content to the NIH’s pioneering open repository, PubMed Central.</p>\n" +
    "\n" +
    "         <p>Heather serves on the Board of Directors of numerous not-for-profit organizations, including the\n" +
    "            <a href=\"http://www.plos.org\">Public Library of Science</a>.  She is a frequent speaker and writer on scholarly communications in general, and on open access in particular.</p>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"board-member\">\n" +
    "         <img src=\"http://i.imgur.com/dVJPqlw.png\" height=100/>\n" +
    "         <p><strong>Ethan White</strong> is an Associate Professor at Utah State University. He studies ecological systems using data-intensive approaches and is actively involved in open approaches to science. He has written papers on <a href=\"http://dx.doi.org/10.4033/iee.2013.6b.6.f\">data management and sharing</a>, <a href=\"http://dx.doi.org/10.1371/journal.pbio.1001745\">best practices in computational science</a>, and <a href=\"http://dx.doi.org/10.1371/journal.pbio.1001563\">the benefits of preprints in biology</a>.</p>\n" +
    "         <p>Ethan has a PhD in Biology from the University of New Mexico, was a National Science Foundation Postdoctoral Fellow in biological informatics, and is the recipient of a National Science Foundation CAREER 'Young Investigators' Award. He speaks frequently about data-intensive approaches to ecology, co-writes a <a href=\"http://jabberwocky.weecology.org\">blog on ecology, academia, and open science</a>, develops material and serves as an instructor for <a href=”http://software-carpentry.org/”>Software Carpentry</a>, and is active on Twitter(<a href=\"https://twitter.com/ethanwhite/\">@ethanwhite</a>).</p>\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"board-member\">\n" +
    "         <img src=\"http://static.tumblr.com/2d33e55fcae6625ea29a0ea14e6b99df/5mlmvbq/O15n1w7ty/tumblr_static_headshot_informal.jpg\" height=100/>\n" +
    "         <p><strong>John Wilbanks</strong> works at <a href=\"http://www.sagebase.org/our-leadership/\">Sage Bionetworks</a>, which helps build <a href=\"http://www.sagebase.org/governance/\">tools and policies</a> that help <a href=\"http://www.sagebase.org/bridge/\">networks of people who have their health data</a> share it with <a href=\"http://synapse.sagebase.org\">networks of people who like to analyze health data</a>.\n" +
    "         </p>\n" +
    "         <p>Previously, John worked at Harvard’s <a href=\"http://cyber.law.harvard.edu\">Berkman Center for Internet &amp; Society</a>, the <a href=\"http://www.w3.org/2001/sw/\" title=\"Semantic Web - World Wide Web Consortium\" target=\"_self\">World Wide Web Consortium</a>, the <a href=\"http://en.wikipedia.org/wiki/Pete_Stark\" title='Fortney \"Pete\" Stark' target=\"_self\">US House of Representatives</a>, <a href=\"http://creativecommons.org\" title=\"Creative Commons\" target=\"_self\">Creative Commons</a>, and the <a href=\"http://kauffman.org\">Ewing Marion Kauffman Foundation</a>. John also serves on the board of the non-profit\n" +
    "            <a href=\"http://earthsciencefoundation.org/\">Foundation for Earth Science</a> and advisory boards for companies including <a href=\"http://www.boundlesslearning.com/\">Boundless Learning</a>,  <a href=\"http://www.crunchbase.com/company/curious-inc\">Curious</a>,  <a href=\"http://genomera.com\">Genomera</a>, <a href=\"http://www.qualcommlife.com/\">Qualcomm Life</a>, <a href=\"http://patientslikeme.com\">Patients Like Me</a>, and <a href=\"http://www.genospace.com/\">GenoSpace</a>.</p>\n" +
    "      </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "      <div id=\"contact\">\n" +
    "         <h3>Contact</h3>\n" +
    "         <p>We'd love to hear your feedback, ideas, or just chat! Reach us at <a href=\"mailto:team@impactstory.org\">team@impactstory.org</a> or on <a href=\"http://twitter.com/Impactstory\">twitter</a>.\n" +
    "      </div>\n" +
    "\n" +
    "\n" +
    "   </div><!-- end wrapper -->\n" +
    "</div>");
}]);

angular.module("about-pages/search.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("about-pages/search.tpl.html",
    "<div class=\"page search\">\n" +
    "    <h2>Search for people</h2>\n" +
    "\n" +
    "    <div class=\"main\" ng-show=\"!loading\">\n" +
    "        <md-autocomplete\n" +
    "                md-selected-item=\"ctrl.selectedItem\"\n" +
    "                md-search-text=\"ctrl.searchText\"\n" +
    "                md-selected-item-change=\"onSearchSelect(person)\"\n" +
    "                md-items=\"person in search(ctrl.searchText)\"\n" +
    "                md-item-text=\"person.name\"\n" +
    "                md-min-length=\"3\"\n" +
    "                md-autofocus=\"true\">\n" +
    "\n" +
    "            <md-item-template>\n" +
    "                <span class=\"search-item\" md-highlight-text=\"ctrl.searchText\">{{person.name}}</span>\n" +
    "            </md-item-template>\n" +
    "\n" +
    "        </md-autocomplete>\n" +
    "        <p>\n" +
    "            You're searching against\n" +
    "            <span class=\"count\">{{ numProfiles }}</span>\n" +
    "            Impactstory profiles.\n" +
    "        </p>\n" +
    "    </div>\n" +
    "</div>");
}]);

angular.module("badge-page/badge-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("badge-page/badge-page.tpl.html",
    "<div class=\"page badge-page\">\n" +
    "    <a href=\"/u/{{ person.orcid_id }}\" class=\"back-to-profile\">\n" +
    "        <i class=\"fa fa-chevron-left\"></i>\n" +
    "        Back to {{ person.given_names }}'s profile\n" +
    "\n" +
    "    </a>\n" +
    "    <div class=\"who-earned-it\">\n" +
    "        {{ person.given_names }} earned this badge\n" +
    "        <span class=\"earned-time\">\n" +
    "         {{ moment(badge.created).fromNow() }}:\n" +
    "        </span>\n" +
    "    </div>\n" +
    "\n" +
    "    <h2>\n" +
    "        <i class=\"fa fa-circle badge-level-{{ badge.level }}\"></i>\n" +
    "        <span class=\"name\">\n" +
    "            {{ badge.display_name }}\n" +
    "        </span>\n" +
    "    </h2>\n" +
    "    <div class=\"various-descriptions\">\n" +
    "        <div class=\"description\">\n" +
    "            {{ badge.description }}\n" +
    "        </div>\n" +
    "        <div class=\"extra-description\" ng-show=\"badge.extra_description\">\n" +
    "            <i class=\"fa fa-info-circle\"></i>\n" +
    "            <div class=\"text\" ng-bind-html=\"trustHtml(badge.extra_description)\"></div>\n" +
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
    "    <div class=\"support\" ng-show=\"badge.support\">\n" +
    "        <pre>{{ badge.support }}</pre>\n" +
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
    "            GitHub\n" +
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

angular.module("helps.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("helps.tpl.html",
    "\n" +
    "\n" +
    "\n" +
    "<p class=\"def buzz\" ng-show=\"subscoreName=='buzz'\">\n" +
    "    <strong>Buzz</strong> is the volume of discussion (good and bad)\n" +
    "    around your research, represented by\n" +
    "    the count of times your research is discussed online.\n" +
    "</p>\n" +
    "<p class=\"def influence\" ng-show=\"subscoreName=='influence'\">\n" +
    "    <strong>Influence</strong> is the average estimated <em>significance</em> of the sources\n" +
    "    discussing your research: Wikipedia counts for more than Facebook, and a tweeter\n" +
    "    with a million followers counts for more than one with a hundred.\n" +
    "</p>\n" +
    "<p class=\"def openness\" ng-show=\"subscoreName=='openness'\">\n" +
    "    <strong>Openness</strong> is how easy it is for people to actually read and use\n" +
    "    your research, estimated by the percent of your publications in\n" +
    "    <a href=\"https://en.wikipedia.org/wiki/Open_access#Journals:_gold_open_access\">Gold open-access</a>\n" +
    "    journals and repositories.\n" +
    "\n" +
    "</p>\n" +
    "<p class=\"def fun\" ng-show=\"subscoreName=='fun'\">\n" +
    "    <strong>Fun</strong> achievements are Not So Serious.\n" +
    "\n" +
    "</p>");
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

angular.module("person-page/person-page-text.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("person-page/person-page-text.tpl.html",
    "<div class=\"person-page-text\">\n" +
    "    <h1>{{ person.given_names }} {{ person.family_name }}</h1>\n" +
    "\n" +
    "    <h2>Top achievements</h2>\n" +
    "    yay me!\n" +
    "</div>");
}]);

angular.module("person-page/person-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("person-page/person-page.tpl.html",
    "<div ng-show=\"profileStatus=='no_email'\" class=\"page person-incomplete set-email\">\n" +
    "    <div class=\"content\">\n" +
    "\n" +
    "        <h2>Almost ready!</h2>\n" +
    "        <p class=\"instructions\">\n" +
    "            We'll need your email to send you updates when\n" +
    "            your research gets new online attention.\n" +
    "            <span class=\"no-spam\">\n" +
    "                We hate spam too! So we won't send you any.\n" +
    "            </span>\n" +
    "        </p>\n" +
    "        <div class=\"setting-email\" ng-show=\"settingEmail\"></div>\n" +
    "        <form ng-show=\"!settingEmail\" class=\"user-input\" ng-submit=\"submitEmail()\">\n" +
    "            <div class=\"form-group\">\n" +
    "                <input ng-model=\"userForm.email\"\n" +
    "                       type=\"email\"\n" +
    "                       class=\"form-control input-lg\"\n" +
    "                       id=\"user-email\"\n" +
    "                       required\n" +
    "                       placeholder=\"Email\">\n" +
    "            </div>\n" +
    "            <button type=\"submit\" class=\"btn btn-primary btn-lg\">Make my profile!</button>\n" +
    "        </form>\n" +
    "        <div class=\"loading\" ng-show=\"settingEmail\">\n" +
    "            <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "            Setting your email\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "<div ng-show=\"profileStatus=='no_products'\" class=\"page person-incomplete add-products\">\n" +
    "    <div class=\"content\">\n" +
    "\n" +
    "        <h2>Uh-oh, your ORCID is empty!</h2>\n" +
    "        <p class=\"instructions\">\n" +
    "            It looks like your ORCID profile doesn't have any of your publications listed.\n" +
    "            But don't worry&mdash;it takes just as few minutes to add them,\n" +
    "            then you'll be ready to roll on Impactstory, as well as lots of\n" +
    "            other great applications that use ORCID.\n" +
    "        </p>\n" +
    "        <p>\n" +
    "            To begin, visit <a href=\"http://orcid.org/{{ person.orcid_id }}\">your ORCID</a>,\n" +
    "            find the \"Works\" section, and click \"add works.\" The ORCID wizard will walk\n" +
    "            you through some ways to add your publications\n" +
    "            (we've had good luck using the <em>CrossRef</em> and <em>Scopus</em> importers).\n" +
    "            Then come back, sync with ORCID, and you're all set!\n" +
    "        </p>\n" +
    "        <div class=\"refresh\" ng-show=\"!syncing\">\n" +
    "            <div class=\"btn btn-lg btn-primary\" ng-click=\"pullFromOrcid()\">\n" +
    "                <i class=\"fa fa-refresh\"></i>\n" +
    "                Did it, now sync me up!\n" +
    "            </div>\n" +
    "        </div>\n" +
    "        <div class=\"loading\" ng-show=\"syncing\">\n" +
    "            <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "            Syncing with ORCID\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "<div ng-show=\"profileStatus=='all_good'\" class=\"page person\">\n" +
    "\n" +
    "    <div class=\"person-header row\">\n" +
    "        <div class=\"col-md-9 person-about\">\n" +
    "            <div class=\"content\">\n" +
    "                <div class=\"avatar\">\n" +
    "                    <img ng-src=\"{{ person.picture }}\" alt=\"\"/>\n" +
    "                </div>\n" +
    "\n" +
    "                <div class=\"bio\">\n" +
    "                    <h2 class=\"name\">\n" +
    "                       {{ person.given_names }} {{ person.family_name }}\n" +
    "                        <span class=\"accounts\">\n" +
    "                            <a href=\"http://orcid.org/{{ person.orcid_id }}\">\n" +
    "                                <img src=\"static/img/favicons/orcid.ico\" alt=\"\">\n" +
    "                            </a>\n" +
    "                            <a href=\"http://depsy.org/{{ person.depsy_id }}\"\n" +
    "                                    ng-show=\"person.depsy_id\">\n" +
    "                                <img src=\"static/img/favicons/depsy.png\" alt=\"\">\n" +
    "                            </a>\n" +
    "                            <a href=\"http://twitter.com/{{ person.twitter }}\"\n" +
    "                               ng-show=\"person.twitter\"\n" +
    "                               class=\"twitter\">\n" +
    "                                <img src=\"static/img/favicons/twitter.ico\" alt=\"\">\n" +
    "                            </a>\n" +
    "                        </span>\n" +
    "                    </h2>\n" +
    "                    <div class=\"aff\">\n" +
    "                        <span class=\"institution\">{{ person.affiliation_name }}</span>\n" +
    "                        <span class=\"role\">\n" +
    "                            {{ person.affiliation_role_title }}\n" +
    "                        </span>\n" +
    "                    </div>\n" +
    "\n" +
    "                    <div class=\"person-score belt\">\n" +
    "                        <span class=\"subscore {{ subscore.name }}\"\n" +
    "                              ng-class=\"{ unselected: selectedSubscore && selectedSubscore.name != subscore.name}\"\n" +
    "                              ng-click=\"toggleSeletedSubscore(subscore)\"\n" +
    "                              ng-repeat=\"subscore in subscores | orderBy: 'sortOrder' | filter: { name: '!fun' }\">\n" +
    "                            <i class=\"fa fa-{{ getBadgeIcon(subscore.name) }}\"></i>\n" +
    "                            <span class=\"number\">{{ numFormat.decimalToPerc(subscore.perc) }}</span>\n" +
    "                            <span class=\"percent\">%</span>\n" +
    "                        </span>\n" +
    "                    </div>\n" +
    "                    <div class=\"autogenerated\" ng-show=\"!person.claimed_at\">\n" +
    "                        <span class=\"this-is\">\n" +
    "                            This is an <a href=\"about/orcid\">auto-generated profile.</a>\n" +
    "                        </span>\n" +
    "                        <span class=\"claim-this\">\n" +
    "                            To claim it,\n" +
    "                            <a href=\"\" class=\"login\" ng-click=\"authenticate()\">log in with ORCID.</a>\n" +
    "                        </span>\n" +
    "                    </div>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "        <div class=\"col-md-3 person-actions\">\n" +
    "            <div class=\"btn btn-default btn-sm follow\" ng-click=\"follow()\">Follow</div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"tab-controls row tab-overview-{{ tab=='overview' }}\">\n" +
    "        <a class=\"tab overview selected-{{ tab=='overview' }}\" href=\"/u/{{ person.orcid_id }}\">overview</a>\n" +
    "        <a class=\"tab publications selected-{{ tab=='achievements' }}\" href=\"/u/{{ person.orcid_id }}/achievements\">achievements</a>\n" +
    "        <a class=\"tab publications selected-{{ tab=='mentions' }}\" href=\"/u/{{ person.orcid_id }}/mentions\">mentions</a>\n" +
    "        <a class=\"tab publications selected-{{ tab=='publications' }}\" href=\"/u/{{ person.orcid_id }}/publications\">publications</a>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "    <!-- OVERVIEW view -->\n" +
    "    <div class=\"tab-view overview row\" ng-if=\"tab=='overview'\">\n" +
    "        <div class=\"col-md-5\">\n" +
    "            <div class=\"badges widget\">\n" +
    "                <div class=\"widget-header\">\n" +
    "                    <h3>Achievements</h3>\n" +
    "                    <a class=\"more\" href=\"/u/{{ person.orcid_id }}/achievements\">view all</a>\n" +
    "                </div>\n" +
    "                <div class=\"badges-wrapper\"\n" +
    "                     ng-include=\"'badge-item.tpl.html'\"\n" +
    "                     ng-repeat=\"badge in person.overview_badges | orderBy: '-sort_score' | limitTo: 3\">\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"col-md-7 big-col\">\n" +
    "            <div class=\"mentions widget\">\n" +
    "                <div class=\"widget-header\">\n" +
    "                    <h3>Mentions</h3>\n" +
    "                    <a class=\"more\" href=\"/u/{{ person.orcid_id }}/mentions\">view all</a>\n" +
    "                </div>\n" +
    "                <div class=\"channels\">\n" +
    "                    <span class=\"val total-posts\">{{ postsSum }}</span>\n" +
    "                    <span class=\"ti-label\">online mentions across {{ sources.length }} channels:</span>\n" +
    "\n" +
    "                    <span class=\"channel\"\n" +
    "                          ng-class=\"{'more-than-3': $index > 3, 'more-than-8': $index > 8}\"\n" +
    "                          ng-repeat=\"channel in sources | orderBy: '-posts_count'\">\n" +
    "                        <img ng-src=\"/static/img/favicons/{{ channel.source_name }}.ico\"\n" +
    "                             class=\"channel-icon {{ channel.source_name }}\">\n" +
    "                        <span class=\"val\">{{ numFormat.short(channel.posts_count) }}</span>\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"publications widget\">\n" +
    "                <div class=\"widget-header\">\n" +
    "                    <h3>Publications</h3>\n" +
    "                    <a class=\"more\" href=\"/u/{{ person.orcid_id }}/publications\">view all</a>\n" +
    "                </div>\n" +
    "                <div class=\"publication-wrapper\"\n" +
    "                     ng-include=\"'publication-item.tpl.html'\"\n" +
    "                     ng-repeat=\"product in products | orderBy: '-altmetric_score' | limitTo: 3\">\n" +
    "                </div>\n" +
    "\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "    <!-- PUBLICATIONS view -->\n" +
    "    <div class=\"tab-view publications row\" ng-if=\"tab=='publications'\">\n" +
    "        <div class=\"col-md-8 publications-col main-col\">\n" +
    "            <p class=\"hedge\">\n" +
    "                Of <a href=\"http://orcid.org/{{ person.orcid_id }}\" target=\"_blank\">\n" +
    "                {{ person.num_orcid_products }} works with DOIs,\n" +
    "            </a>\n" +
    "                we found\n" +
    "            </p>\n" +
    "            <h3>\n" +
    "                {{ selectedGenre.count || products.length }} recently-discussed\n" +
    "                <span class=\"no-filter\" ng-if=\"!selectedGenre\">\n" +
    "                    publications\n" +
    "                </span>\n" +
    "\n" +
    "                <span class=\"filter\" ng-if=\"selectedGenre\">\n" +
    "                    <span class=\"label label-default\">\n" +
    "                        <span class=\"content\">\n" +
    "                            <i class=\"fa fa-{{ getGenreIcon(selectedGenre.name) }}\"></i>\n" +
    "                            {{ pluralize(selectedGenre.display_name) }}\n" +
    "                        </span>\n" +
    "                        <span class=\"close-button\" ng-click=\"toggleSeletedGenre(selectedGenre)\">&times;</span>\n" +
    "                    </span>\n" +
    "                </span>\n" +
    "            </h3>\n" +
    "            <div class=\"publication-wrapper\"\n" +
    "                 ng-include=\"'publication-item.tpl.html'\"\n" +
    "                 ng-repeat=\"product in products | orderBy: '-altmetric_score' | filter: {genre: selectedGenre.name}\">\n" +
    "            </div>\n" +
    "        </div>\n" +
    "        <div class=\"col-md-4 badges-col small-col\">\n" +
    "\n" +
    "            <div class=\"filter-by-genre\" ng-show=\"genres.length > 1\">\n" +
    "                <h4>Filter by genre</h4>\n" +
    "\n" +
    "                <div class=\"genre-filter filter-option\"\n" +
    "                     ng-repeat=\"genre in genres\"\n" +
    "                     ng-class=\"{ unselected: selectedGenre && selectedGenre.name != genre.name, selected: selectedGenre.name == genre.name }\">\n" +
    "                    <span class=\"close-button\" ng-click=\"toggleSeletedGenre(genre)\">&times;</span>\n" +
    "                    <span class=\"content\" ng-click=\"toggleSeletedGenre(genre)\">\n" +
    "                        <span class=\"name\">\n" +
    "                            <i class=\"fa fa-{{ getGenreIcon(genre.name) }} icon\"></i>\n" +
    "                            {{ pluralize(genre.display_name, genre.count) }}\n" +
    "                        </span>\n" +
    "                        <span class=\"val\">({{ genre.count }})</span>\n" +
    "                    </span>\n" +
    "\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <div class=\"coauthors\" ng-show=\"person.coauthors.length\">\n" +
    "                <h4>Coauthors</h4>\n" +
    "                <div class=\"coauthor\" ng-repeat=\"coauthor in person.coauthors | orderBy: '-sort_score'\">\n" +
    "                    <span >\n" +
    "                        <span class=\"subscores\">\n" +
    "                            <span class=\"subscore buzz\">\n" +
    "                                {{ numFormat.decimalToPerc(coauthor.buzz_perc) }}\n" +
    "                            </span>\n" +
    "                            <span class=\"subscore engagement\">\n" +
    "                                {{ numFormat.decimalToPerc(coauthor.engagement_perc) }}\n" +
    "                            </span>\n" +
    "                            <span class=\"subscore openness\">\n" +
    "                                {{ numFormat.decimalToPerc(coauthor.openness_perc) }}\n" +
    "                            </span>\n" +
    "\n" +
    "                        </span>\n" +
    "                        <a href=\"u/{{ coauthor.orcid_id }}\" class=\"name\">\n" +
    "                            {{ coauthor.name }}\n" +
    "                        </a>\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "    <!-- BADGES view -->\n" +
    "    <div class=\"tab-view badges row\" ng-if=\"tab=='achievements'\">\n" +
    "        <div class=\"col-md-8 main-col\">\n" +
    "            <h3>\n" +
    "                <span ng-show=\"filteredBadges.length\" class=\"amount\">{{ filteredBadges.length }}</span>\n" +
    "                <span ng-show=\"!filteredBadges.length\" class=\"amount\">No</span>\n" +
    "                achievement<span ng-hide=\"filteredBadges.length===1\">s</span>\n" +
    "                <span ng-show=\"filteredBadges.length===0\" class=\"yet\">yet</span>\n" +
    "\n" +
    "                <span class=\"filter\" ng-if=\"selectedSubscore\">\n" +
    "                    <span class=\"filter-intro\">in</span>\n" +
    "                    <span class=\"filter label label-default {{ selectedSubscore.name }}\">\n" +
    "                        <span class=\"content\">\n" +
    "                            <i class=\"icon fa fa-{{ getBadgeIcon(selectedSubscore.name) }}\"></i>\n" +
    "                            {{ selectedSubscore.display_name }}\n" +
    "                        </span>\n" +
    "                        <span class=\"close-button\" ng-click=\"toggleSeletedSubscore(selectedSubscore)\">&times;</span>\n" +
    "                    </span>\n" +
    "                </span>\n" +
    "            </h3>\n" +
    "\n" +
    "            <div class=\"subscore-info\" ng-show=\"selectedSubscore\">\n" +
    "\n" +
    "\n" +
    "                <!-- for all subscores -->\n" +
    "                <div class=\"personalized\">\n" +
    "\n" +
    "\n" +
    "                    <div class=\"def buzz\" ng-show=\"selectedSubscore.name=='buzz'\">\n" +
    "                        <strong>Buzz</strong> is the volume of discussion (good and bad)\n" +
    "                        around your research.\n" +
    "                        <span class=\"stats\">\n" +
    "                            Your work has <span class=\"val\">{{ selectedSubscore.score }}</span> online mentions,\n" +
    "                           putting you in the\n" +
    "                            <span class=\"perc {{ selectedSubscore.name }}\">\n" +
    "                                {{ numFormat.decimalToPerc(selectedSubscore.perc, true) }} percentile\n" +
    "                            </span>\n" +
    "                             of researchers in Buzz.\n" +
    "                            <span class=\"nice\" ng-show=\"selectedSubscore.perc > .5\">Nice!</span>\n" +
    "                        </span>\n" +
    "                    </div>\n" +
    "\n" +
    "                    <div class=\"def influence\" ng-show=\"selectedSubscore.name=='engagement'\">\n" +
    "                        <p>\n" +
    "                            <strong>Engagement</strong> is about <em>how</em> your work is mentioned, accounting\n" +
    "                            for the different impacts of different sources: Wikipedia counts for more than Facebook, and a tweeter\n" +
    "                            with a million followers counts for more than one with a hundred.\n" +
    "                        </p>\n" +
    "                        <p>\n" +
    "                            <span class=\"stats\">\n" +
    "                                <span>\n" +
    "                                    We rank your influence in the\n" +
    "                                    <span class=\"perc {{ selectedSubscore.name }}\">\n" +
    "                                        {{ numFormat.decimalToPerc(selectedSubscore.perc, true) }} percentile\n" +
    "                                    </span>\n" +
    "                                    compared to other researchers.\n" +
    "                                </span>\n" +
    "                                (You can learn <a href=\"/about/data\">more about how we calculate this here.</a>)\n" +
    "                            </span>\n" +
    "                        </p>\n" +
    "                    </div>\n" +
    "\n" +
    "\n" +
    "                    <div class=\"def openness\" ng-show=\"selectedSubscore.name=='openness'\">\n" +
    "                        <strong>Openness</strong> is how easy it is for people to actually read and use\n" +
    "                        your research. You're in the\n" +
    "                        <span class=\"perc {{ selectedSubscore.name }}\">\n" +
    "                            {{ numFormat.decimalToPerc(selectedSubscore.perc, true) }} percentile\n" +
    "                        </span>\n" +
    "                        for openness, based on the proportion of your publications in\n" +
    "                        <a href=\"https://en.wikipedia.org/wiki/Open_access#Journals:_gold_open_access\">Gold open-access</a>\n" +
    "                        journals and repositories.\n" +
    "                    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "                    <div class=\"def fun\" ng-show=\"selectedSubscore.name=='fun' && filteredBadges.length\">\n" +
    "                        <strong>Fun</strong> achievements are Not So Serious.\n" +
    "\n" +
    "                    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "                    <p ng-show=\"filteredBadges.length && selectedSubscore.name != 'fun'\" class=\"badges-intro more-badges {{ selectedSubscore.name }}\">\n" +
    "                        You've also got {{ filteredBadges.length }}\n" +
    "                        achievement<span ng-hide=\"filteredBadges.length===1\">s</span>\n" +
    "                        in\n" +
    "                        <span class=\"subscore-name\">{{ selectedSubscore.display_name }}</span>:\n" +
    "                    </p>\n" +
    "\n" +
    "                    <p ng-show=\"!filteredBadges.length && selectedSubscore.name != 'fun'\" class=\"badges-intro no-more-badges {{ selectedSubscore.name }}\">\n" +
    "                        You don't have any achievements in the\n" +
    "                        <span class=\"subscore-name\">{{ selectedSubscore.display_name }}</span> category yet.\n" +
    "                    </p>\n" +
    "\n" +
    "                    <div class=\"no-fun\" ng-show=\"selectedSubscore.name=='fun' && !filteredBadges.length\">\n" +
    "                        <p>\n" +
    "                            Don't get us wrong, we know you are\n" +
    "                            <a href=\"https://en.wikipedia.org/wiki/Happy_Fun_Ball\" class=\"fun\">super super fun.</a>\n" +
    "                        </p>\n" +
    "\n" +
    "                        <p>\n" +
    "                            Just, in ways our scholarly communication website cannot yet measure.\n" +
    "                            Got an idea for a way we can fix that? Hit us up via\n" +
    "                            <a href=\"http://twitter.com/impactstory\">Twitter</a> or\n" +
    "                            <a href=\"mailto:team@impactstory.org\">email!</a>\n" +
    "                        </p>\n" +
    "                    </div>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "            <div class=\"badges-wrapper\"\n" +
    "                 ng-class=\"\"\n" +
    "                 ng-include=\"'badge-item.tpl.html'\"\n" +
    "                 ng-repeat=\"badge in badges | orderBy: '-sort_score' | filter: {group: selectedSubscore.name} as filteredBadges\">\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "        <div class=\"col-md-4 small-col\">\n" +
    "            <h4>Filter by dimension</h4>\n" +
    "            <div class=\"subscore filter-option {{ subscore.name }}\"\n" +
    "                ng-class=\"{ unselected: selectedSubscore && selectedSubscore.name != subscore.name, selected: selectedSubscore.name == subscore.name }\"\n" +
    "                ng-click=\"toggleSeletedSubscore(subscore)\"\n" +
    "                ng-repeat=\"subscore in subscores | orderBy: 'sortOrder'\">\n" +
    "\n" +
    "                <span class=\"close-button\">&times;</span>\n" +
    "                <span class=\"content\">\n" +
    "                    <span class=\"name\">\n" +
    "                        <i class=\"icon fa fa-{{ getBadgeIcon(subscore.name) }}\"></i>\n" +
    "                        {{ subscore.display_name }}\n" +
    "                    </span>\n" +
    "                    <span class=\"val\" ng-show=\"subscore.badgesCount\">({{ subscore.badgesCount }})</span>\n" +
    "                </span>\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "    <!-- MENTIONS view -->\n" +
    "    <div class=\"tab-view mentions row\" ng-if=\"tab=='mentions'\">\n" +
    "        <div class=\"col-md-8 posts-col main-col\">\n" +
    "            <h3>\n" +
    "                {{ selectedChannel.posts_count || postsSum }} mentions\n" +
    "                <span class=\"no-filter\" ng-if=\"!selectedChannel\">online</span>\n" +
    "                <span class=\"filter\" ng-if=\"selectedChannel\">\n" +
    "                    <span class=\"filter-intro\">on</span>\n" +
    "                    <span class=\"filter label label-default\">\n" +
    "                        <span class=\"content\">\n" +
    "                            <img class=\"icon\" ng-src=\"/static/img/favicons/{{ selectedChannel.source_name }}.ico\">\n" +
    "                            {{ selectedChannel.source_name }}\n" +
    "                        </span>\n" +
    "                        <span class=\"close-button\" ng-click=\"toggleSelectedChannel(selectedChannel)\">&times;</span>\n" +
    "                    </span>\n" +
    "                </span>\n" +
    "            </h3>\n" +
    "            <div class=\"posts-wrapper\"\n" +
    "                 ng-repeat=\"post in posts | orderBy: '-posted_on' | filter: postsFilter as filteredPosts\">\n" +
    "\n" +
    "                <div class=\"post normal\"\n" +
    "                     ng-if=\"$index < d.postsLimit && !(!selectedChannel && post.source=='twitter')\"\n" +
    "                     ng-include=\"'mention-item.tpl.html'\"></div>\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"more\">\n" +
    "                <span class=\"btn btn-default btn-sm\"\n" +
    "                      ng-click=\"d.postsLimit = d.postsLimit + 10\"\n" +
    "                      ng-show=\"d.postsLimit < filteredPosts.length\">\n" +
    "                    <i class=\"fa fa-arrow-down\"></i>\n" +
    "                    See more\n" +
    "                </span>\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"col-md-4 score-col small-col\">\n" +
    "            <h4>Filter by channel</h4>\n" +
    "            <div class=\"channel filter-option {{ channel.source_name }}\"\n" +
    "                ng-class=\"{selected: selectedChannel.source_name==channel.source_name, unselected: selectedChannel && selectedChannel.source_name != channel.source_name}\"\n" +
    "                ng-click=\"toggleSelectedChannel(channel)\"\n" +
    "                ng-repeat=\"channel in sources | orderBy: '-posts_count'\">\n" +
    "\n" +
    "                <span class=\"close-button\">&times;</span>\n" +
    "                <span class=\"content\">\n" +
    "                    <span class=\"name\">\n" +
    "                        <img ng-src=\"/static/img/favicons/{{ channel.source_name }}.ico\">\n" +
    "                        {{ channel.display_name }}\n" +
    "                    </span>\n" +
    "                    <span class=\"val\" ng-class=\"{'has-new': channel.events_last_week_count}\">\n" +
    "                        <md-tooltip ng-if=\"channel.events_last_week_count\">\n" +
    "                            {{ channel.events_last_week_count }} new mentions this week\n" +
    "                        </md-tooltip>\n" +
    "                        ({{ numFormat.short(channel.posts_count) }}\n" +
    "                        <span class=\"new-last-week\"\n" +
    "                              ng-show=\"channel.events_last_week_count\">\n" +
    "                            <i class=\"fa fa-arrow-up\"></i>\n" +
    "                        </span>)\n" +
    "                    </span>\n" +
    "                </span>\n" +
    "\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "    <div class=\"row person-footer\">\n" +
    "        <div class=\"text col-md-8\">\n" +
    "            <span class=\"text\">\n" +
    "                <i class=\"fa fa-unlock\"></i>\n" +
    "                All the data you see here is open for re-use.\n" +
    "            </span>\n" +
    "        </div>\n" +
    "        <div class=\"buttons col-md-4\">\n" +
    "            <a class=\"btn btn-xs btn-default\"\n" +
    "               target=\"_self\"\n" +
    "               href=\"/api/person/{{ person.orcid_id }}\">\n" +
    "                <i class=\"fa fa-cogs\"></i>\n" +
    "                view as JSON\n" +
    "            </a>\n" +
    "        </div>\n" +
    "\n" +
    "    </div>\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "");
}]);

angular.module("product-page/product-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("product-page/product-page.tpl.html",
    "<div class=\"page product-page\">\n" +
    "    <div class=\"row biblio-row\">\n" +
    "        <div class=\"biblio-col col-md-8\">\n" +
    "            <a href=\"/u/{{ person.orcid_id }}/publications\" class=\"back-to-profile\">\n" +
    "                <i class=\"fa fa-chevron-left\"></i>\n" +
    "                Back to {{ person.first_name }}'s publications\n" +
    "            </a>\n" +
    "            <h2 class=\"title\">\n" +
    "                {{ product.title }}\n" +
    "            </h2>\n" +
    "            <div class=\"authors\">\n" +
    "                {{product.authors}}\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"journal\">\n" +
    "                <span class=\"year\">{{product.year}}</span>\n" +
    "                <a href=\"http://doi.org/{{ product.doi }}\" class=\"journal\">\n" +
    "                    {{product.journal}}\n" +
    "                    <i class=\"fa fa-external-link\"></i>\n" +
    "                </a>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"type\">\n" +
    "                <span class=\"oa\" ng-show=\"product.is_oa_repository\">\n" +
    "                    <i class=\"fa fa-unlock-alt\"></i>\n" +
    "                    Open access\n" +
    "                </span>\n" +
    "                <span class=\"oa\" ng-show=\"product.is_oa_journal\">\n" +
    "                    <i class=\"fa fa-unlock-alt\"></i>\n" +
    "                    Open Access\n" +
    "                </span>\n" +
    "                <span class=\"genre\" ng-show=\"product.genre != 'article'\">\n" +
    "                    <!--\n" +
    "                    <i class=\"fa fa-{{ getGenreIcon(product.genre) }}\"></i>\n" +
    "                    -->\n" +
    "                    {{ product.genre }}\n" +
    "                </span>\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "            <div class=\"score\" ng-click=\"altmetricScoreModal()\">\n" +
    "                <img src=\"static/img/favicons/altmetric.ico\" alt=\"\">\n" +
    "                <span class=\"val\">{{ numFormat.short(product.altmetric_score) }}</span>\n" +
    "                <a href=\"https://www.altmetric.com/details/{{ product.altmetric_id }}\"\n" +
    "                   class=\"ti-label\">Altmetric.com score</a>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "    <div class=\"row main-row\">\n" +
    "        <!-- MENTIONS view. copied from the profile page -->\n" +
    "        <div class=\"tab-view mentions row\">\n" +
    "            <div class=\"col-md-8 posts-col main-col\">\n" +
    "                <h3>\n" +
    "                    {{ selectedChannel.posts_count || postsSum }} mentions\n" +
    "                    <span class=\"no-filter\" ng-if=\"!selectedChannel\">online</span>\n" +
    "                    <span class=\"filter\" ng-if=\"selectedChannel\">\n" +
    "                        <span class=\"filter-intro\">on</span>\n" +
    "                        <span class=\"filter label label-default\">\n" +
    "                            <span class=\"content\">\n" +
    "                                <img class=\"icon\" ng-src=\"/static/img/favicons/{{ selectedChannel.source_name }}.ico\">\n" +
    "                                {{ selectedChannel.source_name }}\n" +
    "                            </span>\n" +
    "                            <span class=\"close-button\" ng-click=\"toggleSelectedChannel(selectedChannel)\">&times;</span>\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "                </h3>\n" +
    "                <div class=\"posts-wrapper\"\n" +
    "                     ng-repeat=\"post in posts | orderBy: '-posted_on' | filter: postsFilter as filteredPosts\">\n" +
    "\n" +
    "                    <div class=\"post normal\"\n" +
    "                         ng-if=\"$index < d.postsLimit && !(!selectedChannel && post.source=='twitter')\"\n" +
    "                         ng-include=\"'mention-item.tpl.html'\"></div>\n" +
    "\n" +
    "                </div>\n" +
    "\n" +
    "                <div class=\"more\">\n" +
    "                    <span class=\"btn btn-default btn-sm\"\n" +
    "                          ng-click=\"d.postsLimit = d.postsLimit + 10\"\n" +
    "                          ng-show=\"d.postsLimit < filteredPosts.length\">\n" +
    "                        <i class=\"fa fa-arrow-down\"></i>\n" +
    "                        See more\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"col-md-4 score-col small-col\">\n" +
    "                <h4>Filter by channel</h4>\n" +
    "                <div class=\"channel filter-option {{ channel.source_name }}\"\n" +
    "                    ng-class=\"{selected: selectedChannel.source_name==channel.source_name, unselected: selectedChannel && selectedChannel.source_name != channel.source_name}\"\n" +
    "                    ng-click=\"toggleSelectedChannel(channel)\"\n" +
    "                    ng-repeat=\"channel in sources | orderBy: '-posts_count'\">\n" +
    "\n" +
    "                    <span class=\"close-button\">&times;</span>\n" +
    "                    <span class=\"content\">\n" +
    "                        <span class=\"name\">\n" +
    "                            <img ng-src=\"/static/img/favicons/{{ channel.source_name }}.ico\">\n" +
    "                            {{ channel.display_name }}\n" +
    "                        </span>\n" +
    "                        <span class=\"val\" ng-class=\"{'has-new': channel.events_last_week_count}\">\n" +
    "                            <md-tooltip ng-if=\"channel.events_last_week_count\">\n" +
    "                                {{ channel.events_last_week_count }} new mentions this week\n" +
    "                            </md-tooltip>\n" +
    "                            ({{ numFormat.short(channel.posts_count) }}\n" +
    "                            <span class=\"new-last-week\"\n" +
    "                                  ng-show=\"channel.events_last_week_count\">\n" +
    "                                <i class=\"fa fa-arrow-up\"></i>\n" +
    "                            </span>)\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>");
}]);

angular.module("settings-page/settings-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("settings-page/settings-page.tpl.html",
    "<div class=\"page settings-page\">\n" +
    "    <h2>Settings</h2>\n" +
    "    <a href=\"/u/{{ orcidId }}\" class=\"back-to-profile\">\n" +
    "        <i class=\"fa fa-chevron-left\"></i>\n" +
    "        Back to my profile\n" +
    "\n" +
    "    </a>\n" +
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
    "        <span class=\"btn btn-lg btn-default\" ng-click=\"donate(1000)\">\n" +
    "            <i class=\"fa fa-thumbs-o-up\"></i>\n" +
    "                Donate $10\n" +
    "            </span>\n" +
    "        <span class=\"btn btn-lg btn-default\" ng-click=\"donate(10000)\">\n" +
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

angular.module("sidemenu.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("sidemenu.tpl.html",
    "<div class=\"menu-items\">\n" +
    "    <div class=\"source last-real-source-{{ $last }} first-real-source-{{ $first }}\"\n" +
    "         ng-class=\"{viewThisSource==source.source_name}\"\n" +
    "         ng-click=\"setWorkspace('posts', source.source_name)\"\n" +
    "         ng-repeat=\"source in sources | orderBy: '-posts_count'\">\n" +
    "        <span class=\"favicon\">\n" +
    "            <img ng-src=\"/static/img/favicons/{{ source.source_name }}.ico\">\n" +
    "        </span>\n" +
    "        <span class=\"name\">{{ source.display_name }}</span>\n" +
    "        <span class=\"icon-right\">\n" +
    "            <span class=\"new-last-week\"\n" +
    "                  tooltip=\"{{ source.events_last_week_count }} new this week\"\n" +
    "                  ng-show=\"source.events_last_week_count\">\n" +
    "                <i class=\"fa fa-arrow-up\"></i>\n" +
    "            </span>\n" +
    "            <span class=\"look-right\" ng-show=\"workspace=='posts' && viewThisSource==source.source_name\">\n" +
    "                <i class=\"fa fa-chevron-right\"></i>\n" +
    "            </span>\n" +
    "        </span>\n" +
    "        <span class=\"value\">\n" +
    "            {{ numFormat.short(source.posts_count) }}\n" +
    "        </span>\n" +
    "    </div>\n" +
    "</div>\n" +
    "<a class=\"learn-more\" href=\"about/metrics\">\n" +
    "    <i class=\"fa fa-info-circle\"></i>\n" +
    "    <span class=\"text\">Learn more about metrics</span>\n" +
    "</a>");
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

angular.module("static-pages/landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("static-pages/landing.tpl.html",
    "<!-- the landing page for people who are not logged in -->\n" +
    "<div class=\"landing static-page\">\n" +
    "    <div class=\"above-the-fold\">\n" +
    "        <div class=\"tagline\">\n" +
    "            <h1>\n" +
    "                Find the online impact of your research\n" +
    "            </h1>\n" +
    "            <div class=\"sub\">\n" +
    "                Track buzz on Twitter, blogs, news outlets and more:\n" +
    "                we're like Google Scholar for your research's online reach.\n" +
    "                Making a profile takes just seconds:\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"join-button\">\n" +
    "            <md-button class=\"md-accent md-raised\" ng-click=\"authenticate()\">Join for free with ORCID</md-button>\n" +
    "            <span class=\"no-orcid\" ng-click=\"noOrcid($event)\">\n" +
    "                <i class=\"fa fa-question-circle\"></i>\n" +
    "                I don't have an ORCID\n" +
    "            </span>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"featured-in\">\n" +
    "        <h4>\n" +
    "            Featured in\n" +
    "            <i class=\"fa fa-chevron-down\"></i>\n" +
    "        </h4>\n" +
    "        <div class=\"logos\">\n" +
    "            <img src=\"static/img/nature.png\">\n" +
    "            <img src=\"static/img/science.png\">\n" +
    "            <img src=\"static/img/chronicle.png\" class=\"dark\">\n" +
    "            <img src=\"static/img/bbc.png\">\n" +
    "        </div>\n" +
    "    </div>\n" +
    "\n" +
    "    <div class=\"landing-footer\">\n" +
    "        <div class=\"links col\">\n" +
    "            <a href=\"about\">About</a>\n" +
    "            <a href=\"http://twitter.com/impactstory\">Twitter</a>\n" +
    "            <a href=\"https://github.com/Impactstory/impactstory-tng\">Source code</a>\n" +
    "            <a href=\"mailto:team@impactstory.org\">Email</a>\n" +
    "        </div>\n" +
    "        <div class=\"funders col\">\n" +
    "            Supported by the\n" +
    "            <span class=\"funder\">the National Science Foundation</span>\n" +
    "            <span class=\"funder second\">and Alfred P. Sloan Foundation</span>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "<script type=\"text/ng-template\" id=\"orcid-dialog.tmpl.html\">\n" +
    "<md-dialog aria-label=\"Mango (Fruit)\"  ng-cloak>\n" +
    "        <md-dialog-content>\n" +
    "            <div class=\"md-dialog-content\">\n" +
    "                <p>Signing up for Impactstory requires an ORCID ID.  But don't worry, getting an ORCID ID is fast and free.\n" +
    "                <p>ORCID IDs are used to identify scholars, unambiguously linking them to their publications.  ORCID IDs are administered by a global, international, non-profit organization. Signing up for an ORCID ID is free, quick, and is increasingly required by funders, journals, and academic employers.</p>\n" +
    "            </div>\n" +
    "        </md-dialog-content>\n" +
    "    <md-dialog-actions layout=\"row\">\n" +
    "        <md-button ng-click=\"modalAuth()\">Get my ORCID!</md-button>\n" +
    "    </md-dialog-actions>\n" +
    "\n" +
    "</md-dialog>\n" +
    "</script>\n" +
    "");
}]);

angular.module("static-pages/login.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("static-pages/login.tpl.html",
    "<div id=\"login-blank\">\n" +
    "   <div id=\"login-loading\">\n" +
    "      <div class=\"content\">\n" +
    "         <md-progress-circular class=\"md-primary\"\n" +
    "                               md-diameter=\"170\">\n" +
    "         </md-progress-circular>\n" +
    "         <h2>Getting your profile...</h2>\n" +
    "         <img src=\"static/img/impactstory-logo-sideways.png\">\n" +
    "      </div>\n" +
    "   </div>\n" +
    "</div>");
}]);

angular.module("workspace.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("workspace.tpl.html",
    "\n" +
    "<!-- achievments workspace -->\n" +
    "<div class=\"workspace-view row achievements\" ng-if=\"workspace=='achievements'\">\n" +
    "    <div class=\"achievements-list\">\n" +
    "        <div class=\"achievements workspace-item\"\n" +
    "             ng-class=\"{'featured': $index < 3}\"\n" +
    "             ng-repeat=\"badge in badges | orderBy: '-sort_score' | limitTo: badgeLimit \">\n" +
    "            <div class=\"icon\">\n" +
    "                <i class=\"fa {{ getBadgeIcon(badge.group) }}\"></i>\n" +
    "            </div>\n" +
    "            <div class=\"content\">\n" +
    "                <div class=\"title\">\n" +
    "                    <a href=\"/u/{{ person.orcid_id }}/badge/{{ badge.name }}\">\n" +
    "                        {{badge.display_name}}\n" +
    "                    </a>\n" +
    "                </div>\n" +
    "                <div class=\"under\">\n" +
    "                    {{ badge.description }}\n" +
    "                </div>\n" +
    "                <div class=\"earned-on\" ng-show=\"badge.is_for_products\">\n" +
    "                    Earned on\n" +
    "                    <a href=\"/u/{{ person.orcid_id }}/badge/{{ badge.name }}\">\n" +
    "                        {{ badge.dois.length }} products\n" +
    "                    </a>\n" +
    "                </div>\n" +
    "                <div class=\"earned-on\" ng-show=\"!badge.is_for_products\">\n" +
    "                    Earned on whole profile\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "        <div class=\"show-more\"\n" +
    "             ng-show=\"badgeLimit==3 && badges.length > 3\"\n" +
    "             ng-click=\"badgeLimit=999999999\">\n" +
    "            <i class=\"fa fa-chevron-down\"></i>\n" +
    "            show {{ badges.length - 3 }} more\n" +
    "        </div>\n" +
    "        <div class=\"show-fewer\" ng-show=\"badgeLimit > 3\" ng-click=\"badgeLimit=3\">\n" +
    "            <i class=\"fa fa-chevron-up\"></i>\n" +
    "            show fewer\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "<!-- products workspace -->\n" +
    "<div class=\"workspace-view row products\" ng-if=\"workspace=='products'\">\n" +
    "    <div class=\"products-list\">\n" +
    "        <div class=\"products workspace-item\"\n" +
    "             ng-repeat=\"product in products | orderBy : '-altmetric_score'\">\n" +
    "            <div class=\"icon\">\n" +
    "                <i class=\"fa fa-file-text-o\"></i>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"content\">\n" +
    "                <div class=\"title\">\n" +
    "                    <a href=\"u/{{person.orcid_id}}/product/doi/{{ product.doi }}\">{{ product.title }}</a>\n" +
    "                </div>\n" +
    "                <div class=\"under\">\n" +
    "                    <span class=\"year date\">{{ product.year }}</span>\n" +
    "                    <span class=\"attr\">\n" +
    "                        {{ product.journal }}\n" +
    "                        <span class=\"oa-icon oa-journal\" ng-show=\"product.is_oa_journal\">\n" +
    "                            <md-tooltip>\n" +
    "                                This is an Open Access journal\n" +
    "                            </md-tooltip>\n" +
    "                            <i class=\"fa fa-unlock-alt\"></i>\n" +
    "                        </span>\n" +
    "                        <span class=\"oa-icon oa-journal\" ng-show=\"product.is_oa_repository\">\n" +
    "                            <md-tooltip>\n" +
    "                                This is an open-access repository\n" +
    "                            </md-tooltip>\n" +
    "                            <i class=\"fa fa-unlock-alt\"></i>\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "                <div class=\"source-icons\">\n" +
    "            <span class=\"source-icon\"\n" +
    "                  ng-repeat=\"source in product.sources | orderBy: 'display_name'\">\n" +
    "                <md-tooltip md-direction=\"top\">\n" +
    "                    {{ source.posts_count }} {{source.display_name }}\n" +
    "                </md-tooltip>\n" +
    "                <img ng-src=\"/static/img/favicons/{{ source.source_name }}.ico\" class=\"{{source.source_name}}\">\n" +
    "            </span>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "            <div class=\"metric\">\n" +
    "                <md-tooltip md-direction=\"top\">\n" +
    "                    Altmetric.com score\n" +
    "                </md-tooltip>\n" +
    "                {{ numFormat.short(product.altmetric_score) }}\n" +
    "                <i class=\"fa fa-arrow-up\" ng-show=\"product.events_last_week_count > 0\"></i>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "<!-- posts workspace -->\n" +
    "<div class=\"workspace-view row posts\" ng-if=\"workspace=='posts'\">\n" +
    "    <div class=\"posts-list\">\n" +
    "        <div class=\"posts workspace-item\"\n" +
    "             ng-repeat=\"post in posts | orderBy: '-posted_on' | filter: {source: viewThisSource}\">\n" +
    "            <div class=\"icon\">\n" +
    "                <img ng-src=\"/static/img/favicons/{{ post.source }}.ico\">\n" +
    "            </div>\n" +
    "            <div class=\"content\">\n" +
    "                <div class=\"title\">\n" +
    "                    <a href=\"{{ post.url }}\">\n" +
    "                        {{post.title}}\n" +
    "                        <i class=\"fa fa-external-link\"></i>\n" +
    "                    </a>\n" +
    "                </div>\n" +
    "                <div class=\"under\">\n" +
    "                    <span class=\"date\">\n" +
    "                        <md-tooltip>\n" +
    "                            Posted on\n" +
    "                            {{ moment(post.posted_on).format(\"dddd, MMMM Do YYYY, h:mm:ss a\") }}\n" +
    "                        </md-tooltip>\n" +
    "\n" +
    "                        <span class=\"human-readable\">\n" +
    "                            {{ moment(post.posted_on).fromNow() }}\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "                    <span class=\"attr\">{{post.attribution}}</span>\n" +
    "                    cited\n" +
    "                    <a href=\"/u/{{person.orcid_id}}/product/doi/{{ post.citesDoi }}\">\n" +
    "                        {{ post.citesTitle }}\n" +
    "                    </a>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "<!-- twitter workspace -->\n" +
    "<div class=\"workspace-view row tweeters\" ng-if=\"workspace=='twitter'\">\n" +
    "    <div class=\"tweeters-list\">\n" +
    "        <div class=\"tweeters workspace-item\"\n" +
    "             ng-repeat=\"tweeter in tweeters | orderBy: '-followers' | limitTo: 25\">\n" +
    "\n" +
    "            <div class=\"icon\">\n" +
    "                <img ng-src=\"{{ tweeter.img }}\">\n" +
    "            </div>\n" +
    "            <div class=\"content\">\n" +
    "                <div class=\"title\">\n" +
    "                    <a href=\"{{ tweeter.url }}\">\n" +
    "                        {{tweeter.name}}\n" +
    "                    </a>\n" +
    "                    <span class=\"extra\">\n" +
    "                        <span class=\"count\">\n" +
    "                            {{  numFormat.short(tweeter.followers) }}\n" +
    "                        </span>\n" +
    "                        followers\n" +
    "                    </span>\n" +
    "                </div>\n" +
    "                <div class=\"under\">\n" +
    "                    <span class=\"attr\">{{tweeter.description}}</span>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "    </div>\n" +
    "</div>");
}]);

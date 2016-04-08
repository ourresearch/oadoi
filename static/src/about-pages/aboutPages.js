angular.module('aboutPages', [])



    .config(function($routeProvider) {
        $routeProvider.when('/about/metrics', {
            templateUrl: 'about-pages/about-metrics.tpl.html',
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
                                           BadgeDefs,
                                           badgesResp){
        $scope.badgeDefs = BadgeDefs

        // copied from person page
        var subscoreSortOrder = {
            buzz: 1,
            influence: 2,
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




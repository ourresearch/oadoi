angular.module('aboutPages', [])



    .config(function($routeProvider) {
        $routeProvider.when('/about/metrics', {
            templateUrl: 'about-pages/about-metrics.tpl.html',
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
        $routeProvider.when('/about/badges', {
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

    .controller("searchPageCtrl", function($scope, $http){
        $scope.ctrl = {}

        $scope.search = function(searchName) {
            $http.get("api/search/" + searchName)
                .success(function(resp){
                    $scope.ctrl = "foo"
                })
        }
    })


    .controller("aboutPageCtrl", function($scope,
                                          $auth,
                                           $routeParams,
                                           Person,
                                           BadgeDefs,
                                           badgesResp){
        $scope.badgeDefs = BadgeDefs

        var sortLevel = {
            "gold": 1,
            "silver": 2,
            "bronze": 3
        }

        // convert to a list in a kinda dumb way, whatevs.
        var badgesList = []
        _.each(BadgeDefs.d, function(v, k){
            var myBadge = _.extend({}, v);
            myBadge.id = k
            myBadge.sortLevel = sortLevel[myBadge.level]
            badgesList.push(myBadge)
        })

        // group the badges by Badge Group
        var badgesByGroup = _.groupBy(badgesList, "group")
        var badgeGroups = []
        _.each(badgesByGroup, function(badges, groupName){
            var aggregationLevel
            if (badges[0].is_for_products){
                aggregationLevel = "product"
            }
            else {
                aggregationLevel = "person"
            }

            badgeGroups.push({
                name: groupName,
                badges: badges,
                aggregationLevel: aggregationLevel
            })
        })

        // group everything by Aggregation Level (person or product)
        var badges = _.groupBy(badgeGroups, "aggregationLevel")
        $scope.badges = badges


        console.log("these are the badges:", badges)

        if ($auth.isAuthenticated()){
            var myOrcidId = $auth.getPayload()["sub"]
            Person.load(myOrcidId).success(function(resp){
                console.log("loaded the person", Person.d)
                $scope.iHaveThisBadge = function(badgeId){
                    return _.findWhere(Person.d.badges, {name: badgeId})
                }
            })
        }









    })




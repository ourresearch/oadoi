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




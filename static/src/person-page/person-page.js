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
        console.log("retrieved the person", $scope.person)

        var badgeColsDict = {
            gold: [],
            silver: [],
            bronze: [],
        }

        // put each badge in the correct column.
        _.each(Person.d.badges, function(myBadge){
            console.log("testing badgedefs for name", myBadge.name)
            var level = BadgeDefs.d[myBadge.name].level

            console.log("badge level", level)

            badgeColsDict[level].push(myBadge)
        })

        // ok the badge columns are all set up, put in scope now.
        $scope.badgeCols = [
            {level: "gold", list: badgeColsDict.gold},
            {level: "silver", list: badgeColsDict.silver},
            {level: "bronze", list: badgeColsDict.bronze}
        ]

        console.log("badges: ", $scope.badgeCols)









    })




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




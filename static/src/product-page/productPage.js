angular.module('productPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/product/:namespace/:id*', {
            templateUrl: 'product-page/product-page.tpl.html',
            controller: 'productPageCtrl'
            ,
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



    .controller("productPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){



        console.log("loaded the product controller")
        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs
        console.log("retrieved the person", $scope.person)

        var doi = $routeParams.id // all IDs are DOIs for now.
        $scope.product = _.findWhere(Person.d.products, {doi: doi})
        console.log("$scope.product", $scope.product)

        $scope.altmetricScoreModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title('The Altmetric.com score')
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                //.targetEvent(ev)
                .clickOutsideToClose(true)
                .ok('ok')
                .cancel('Learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                console.log("learn more")
                $location.path("about/metrics")
            });
        };


        var badgesWithConfigs = Person.getBadgesWithConfigs(BadgeDefs.d)
        var badgesForThisProduct = _.filter(badgesWithConfigs, function(badge){
            return badge.is_for_products && _.contains(badge.dois, doi)
        })

        $scope.badges = badgesForThisProduct

        //var groupedByLevel = _.groupBy(badgesForThisProduct, "level")
        //
        //// ok the badge columns are all set up, put in scope now.
        //$scope.badgeCols = [
        //    {level: "gold", list: groupedByLevel.gold},
        //    {level: "silver", list: groupedByLevel.silver},
        //    {level: "bronze", list: groupedByLevel.bronze}
        //]










    })



